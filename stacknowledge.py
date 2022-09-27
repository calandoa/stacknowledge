#!/usr/bin/python

# This script try to compute stack usage from compiled C sources files.
# Use gcc with '-fstack-usage' and '-fdump-final-insns'
#
# Written by Antoine Calando / 2022 - Public domain

import argparse
import fileinput
import os
import re
import sys

import configparser
from fnmatch import fnmatch


# Utility functions
def print_err(text):
	sys.stderr.write("ERROR: " + text + "\n")
	sys.exit(1)

def print_warn(text):
	sys.stderr.write("WARNING: " + text + "\n")


def print_dbg(text):
	sys.stderr.write("DBG: " + text + "\n")


# Special cases for stack usage put in su_extra
class SuExtra:
	su = 0

class SuLibrary(SuExtra):
	# Lib call
	txt = 'LIB'
	def __init__(self, fn):
		self.fn = fn

class SuDynamic(SuExtra):
	# Pointer call
	txt = 'DYN'
	def __init__(self, pos):
		self.pos = pos

	def __eq__(self, oth):
		return self.pos == oth.pos
	def __hash__(self):
		return hash(self.pos)

class SuVLA(SuExtra):
	# Variable length array (not managed yet)
	txt = 'VLA'

class SuCycle(SuExtra):
	# Recursion
	txt = 'CYC'
	spec = False
	def __init__(self, fpath, fo):
		# Path goes from first function part of the cycle to the last calling the first
		idx = fpath.index(fo)
		self.path = fpath[idx:]

		str = ' '.join([ p.name for p in self.path])

		print('Cycle detected!', str, fo.name)

		# Put -1 in last function SU
		idx = self.path[-1].call.index(fo)
		self.path[-1].call_su[idx] = -1

		su_cum = 0
		for fo in self.path:
			fo.su_extra.add(self)
			self.su += fo.su

		# assume 10 iterations through cycle
		if arg.output:
			confout.set("cycle", str, '10')

		mul = config.get("cycle", str, fallback = None)
		if mul is None:
			mul = 10
		else:
			self.spec = True

		self.su *= int(mul)



class Func:
	def __init__(self, name, file):
		self.name = name	# func name
		self.file = [ file ]	# filename (may be >1 for static func)
		self.src = None		# file + pos in src
		self.call = set()	# 1st pass: set of func name strings, 2nd pass: list of Func objs
		self.call_su = []	# su cumulated for each 'call' obj
		self.call_dyn = []   	# list of filepos of dynamic call
		self.ref = set()	# ref to symbol except static call
		self.su = None		# stack usage local
		self.su_cum = 0		# su cumulated
		self.su_extra = set()	# stack usage local
		self.called = []	# funcs obj calling this func
		self.refed = []		# funcs obj ref'ing (except static call) this func
		self.cycle = False	# flag to detect recursion
		self.done = False	# flag to detect processing


	def info(self):
		print("Func: ", self.name,  ' (', ' '.join(self.file) if self.file[0]  else 'LIB', ')', sep = '')
		print("\tsrc:", self.src)

		su = 0
		txt = ""
		for x in self.su_extra:
			su += x.su
			txt += x.txt + ' '
		print("\tstack loc:", self.su, "  cumul:", self.su_cum + su, "  (" + txt[:-1] + ")" if txt else "")
		if self.call:
			print("\tcall:", end='')
			for co, csu in zip(self.call, self.call_su):
				print('', co.name, '(' + str(csu) + ') ', end='')
			print()
		if self.call_dyn:
			print("\tcall dyn:")
			for do in self.call_dyn:
				print('\t\t', do)
		if self.ref:
			print("\tref:", end='')
			for r in self.ref:
				print('', r, end='')
			print()

		if self.called:
			print("\tcalled by:",end='')
			for co in self.called:
				print('', co.name, end='')
			print()

		if self.refed:
			print("\trefed by:", end='')
			for r in self.refed:
				print('', r, end='')
			print()

		for x in self.su_extra:
			if type(x) is SuDynamic:
				print ("\tDYN:", x.pos)
			elif type(x) is SuLibrary:
				print ("\tLIB:", x.fn)
			elif type(x) is SuCycle:
				print ("\tCYC:", [fo.name for fo in x.path], x.su)
			else:
				print("\tEXTRA not managed")

		print()



config = None
confout = None
arg = None

def stacknowledge():
	global config, confout, arg

	# Command line argument parsing
	parser = argparse.ArgumentParser()

	#parser.add_argument("-d", "--debug", help="Debugging", action="store_true")
	parser.add_argument("-c", "--config", help="Provide config file")
	parser.add_argument("-o", "--output", help="Generate config file template")
	parser.add_argument("files_rtl",	  help="GCCs RTL .expand file", nargs="+")

	parser.parse_args()
	arg = parser.parse_args()

	# Input config file to tune processing
	config = configparser.ConfigParser(allow_no_value=True)
	config.optionxform = lambda s: s
	if arg.config:
		config.read(arg.config)

	# Output config file to help user to write an input one
	if arg.output:
		confout = configparser.ConfigParser(allow_no_value=True, delimiters=':')
		confout.add_section("multiple")
		confout.add_section("cycle")
		confout.optionxform = lambda s: s


	print("\nCheck all filenames...")
	files_su = []
	for file in arg.files_rtl:
		# Check if RTL files from arg can be read
		if not os.path.isfile(file) or not os.access(file, os.R_OK):
			print_err("Cannott open rtl file \"{}\"!".format(file))

		# Generate stack usage filenames and check files
		file_su = file
		while file_su:
			for ext in ('.su', '.c.su', '.o.su'):
				if os.path.isfile(file_su + ext):
					files_su += [file_su + ext]
					file_su = None
					break
			else:
				file_su = file_su[:file_su.rfind('.')]

	# Regex to parsecall and ref instruction
	function = re.compile(r"^;; Function ([^(]*)\s+\((\S+)(,.*)?\).*$")	# g1 is C/C++ src name, g2 is link name
	call = re.compile(r"^.*\(call [^\")]*\"([^\"]*)\".*$")			# g1 is called name
	call_dyn = re.compile(r"^.*\(call .*$")					# no group
	symbol_ref = re.compile(r"^.*\(symbol_ref[^\"]*\"([^\"]*)\".*$")	# g1 is object name outside call
	filepos = re.compile(r".*(\"[^\"]+.[ch]\":[0-9]+:[0-9]+)#.*")		# g1 is "filename":pos:col

	# Main functions dictionary { name : class Func }
	functions = {}

	print("\nParse all RTL files (might take a few seconds)...")

	finput = fileinput.FileInput(arg.files_rtl)
	src = True
	while True:
		# append lines until matching '(' and ')' at root level
		opn = 0
		cls = 0
		line = ''
		filename = finput.filename()
		for pline in finput:
			pline = pline[:-1]
			opn += pline.count('(')
			cls += pline.count(')')
			line += pline
			if opn == cls:
				break
		else:
			break

		# Find function entry point
		match = re.match(function, line)
		if match is not None:
			fn = match.group(2)
			fo = functions.get(fn)
			if fo is None:
				fo = Func(fn, filename)
				functions[fn] = fo
			else:
				# Function name already added
				fo.file += [ filename ]
				#print_warn("Function {} defined in multiple files:\n\t\"{}\"!". format(fn, ', '.join(fo.file)))
			src = False
			continue

		if not src:
			# After function entry point, parse each line for filename to locate func definition in src
			match = re.match(filepos, line)
			if match is not None:
				src = match.group(1)
				if fo.src is not None :
					# Def positon already added, check if it is the same
					if fo.src == src:
						#print_warn("Function with mutiple defined has same orig: " + src)
						pass
					elif not config.has_option("multiple", fn):
						print_warn("Function with mutiple defs has diff orig!!!: " + src + ' ' + fo.src)
						if arg.output:
							confout.set("multiple", fo.name, None)
				else:
					fo.src = src

		# Find direct function call
		match = re.match(call, line)
		if match is not None:
			fo.call.add(match.group(1))
			continue

		# Find dynamic function call
		match = re.match(call_dyn, line)
		if match is not None:
			fo.call_dyn.append(re.match(filepos, line).group(1))
			continue

		# Find non-call references
		match = re.match(symbol_ref, line)
		if match is not None:
			ref = match.group(1)
			if not ref.startswith("*.L"):
				fo.ref.add(ref)
			continue

	print("\nParse all stack usage files...")
	for line in fileinput.input(files_su):

		#name.c:line:char:func_name	 usage	  static
		fn, su, kw = line[:-1].split(':')[3].split('\t')
		if fn.endswith('constprop'):
			fn += '.0'

		if kw != 'static':
			print_warn("Non 'static' satck usage function not managed for:\n\t" + line)

		fo = functions.get(fn)
		if fn is None:
			print_warn("stack usage for unkown function: " + fn)
		elif fo.su is not None:
			if fo.su == int(su):
				#print_warn("stack usage defined multiple times for function (and ==): " + fn)
				pass
			else:
				print_warn("stack usage defined multiple times for function (but !=): " + fn)
		else:
			fo.su = int(su)

	# Functions parsed but not statically called
	roots = []
	# Functions parsed and referenced outside a call (e.g. stored in a function pointer for a dynamic call)
	refs = []
	# Functions listed in config file "dynamic" section and to be excluded from refs
	refs_out = []
	# Functions parsed but doing no call
	leaves = []
	# Functions not found in C sources (ext lib or asm)
	ext_functions = {}
	# Objects referenced but nt part of functions parsed (e.g. outside func or global var)
	ext_obj = set()
	# Functions parsed and calling via pointer
	dynamic = []

	print("\nFunction analysis 1st pass...")
	for fn, fo in functions.items():

		# Replace call set() of string by list of obj ref
		lcall = []
		for fcn in fo.call:
			fco = functions.get(fcn)
			if fco:
				fco.called += [ fo ]
				lcall += [ fco ]
			else:
				ext = ext_functions.setdefault(fcn, Func(fcn, None))
				ext.called += [ fo ]

				lcall += [ ext ]
		fo.call = lcall
		fo.call_su = [ None ] * len(lcall)

		# Check if objects referenced are know functions or var/external
		for frn in fo.ref:
			fro = functions.get(frn)
			if fro:
				fro.refed += [fn]
			else:
				ext_obj |= { frn }

		# Try to link dynamic calls from RTL with config desc
		confdyn = config.get("dynamic", fn, fallback = "").split()
		if fo.call_dyn:
			dynamic += [fo]
			for fcn in confdyn:
				fco = functions.get(fcn)
				if fco:
					fco.called.append(fo)
					fo.call.append(fco)
					fo.call_su.append(None)
					refs_out.append(fco)
				else:
					print_err("function in dynamic section not found: " + fcn)


			# if not all call given in config, cannot identify
			if len(fo.call_dyn) > len(confdyn):
				for pos in fo.call_dyn:
					fo.su_extra.add(SuDynamic(pos))

		elif len(fo.call) == 0:
			leaves += [fo]

		if fo.su is None:
			print_warn("stack usage not found for function: " + fn)
			fo.su = 0

		# Stack usage file fro gcc drops the .0
		if 'constprop' in fn and 'constprop.0' not in fn:
			print_warn("constprop function not '.0' (not managed!): " + fn)


	print("\nFunction analysis 2nd pass...")
	for fn, fo in functions.items():
		if not fo.called:
			roots += [fo]

		if fo.refed and fo not in refs_out:
			refs += [fo]


	# Identify potential recursion by descending into call graph
	print("\nCycle pass...")
	def tree_downward(fo, path):
		if fo.done:
			return
		if fo.cycle:
			SuCycle(path, fo)
		else:
			fo.cycle = True
			path.append(fo)
			for fco in fo.call:
				tree_downward(fco, path)
			fo.cycle = False
			path.pop()
			fo.done = True

	for fo in roots:
		path = []
		tree_downward(fo, path)


	#for fn, fo in functions.items():
	#	fo.info()


	#print("\nList functions:")
	#for fn, fo in functions.items():
	#	fo.info()
	#sys.exit(0)

	# Compute stack usage by computing it from the leaves
	print("\nSU calculation pass...")
	def tree_upward(fo):
		for fbo in fo.called:
			idx = fbo.call.index(fo)
			# -1 is put in last func of cycle to prevent looping forever
			if fbo.call_su[idx] == -1:
				continue

			fbo.call_su[idx] = fo.su_cum
			fbo.su_extra |= fo.su_extra
			# If stack usage computed for all call, take the highest and continue upward
			if None not in fbo.call_su:
				fbo.su_cum = max(fbo.call_su) + fbo.su
				tree_upward(fbo)


	for fn, fo in ext_functions.items():
		su = config.get("library", fn, fallback = None)
		if su is None:
			fo.su_extra.add(SuLibrary(fn))
		else:
			fo.su = int(su)
			fo.su_cum = fo.su
		tree_upward(fo)

	for fo in dynamic:
		fo.su_cum = fo.su
		tree_upward(fo)
	for fo in leaves:
		fo.su_cum = fo.su
		tree_upward(fo)


	max_su = [ ( 0, None) ]
	max_cum = [ ( 0, None) ]

	print("\nLast pass:")
	for fn, fo in functions.items():
		# Add cycle su to su_cum
		rem = []
		for x in fo.su_extra:
			if type(x) is SuCycle:
				fo.su_cum += x.su
				if x.spec:
					rem.append(x)

		for x in rem:
			fo.su_extra.remove(x)

		# Keep sorted lists of ax su
		def ins(lst, su, fo):
			for idx, (lsu, lfo) in enumerate(lst):
				if su > lsu:
					lst.insert(idx, (su, fo))
					break
			del lst[11:]

		if fo.su > max_su[-1][0]:
			ins(max_su, fo.su, fo)

		if fo.su_cum > max_cum[-1][0]:
			ins(max_cum, fo.su_cum, fo)

	del max_su[-1]
	del max_cum[-1]

	print("\nList functions:")
	for fn, fo in functions.items():
		fo.info()


	print("\nMax stack usage:")
	for su, fo in max_su:
		print('\t' + str(su) + '\t' + fo.name)

	print("\nMax cumulated stack usage:")
	for su, fo in max_cum:
		print('\t' + str(su) + '\t' + fo.name)


	print("\nEXT FCT:", list(ext_functions))
	#print("\nEXT OBJ:", ext_obj)
	print("\nDYN:", [ fo.name for fo in dynamic])
	print("\nROOT:", [ fo.name for fo in roots])
	#print("\nROOT ref:", [ fo.name for fo in roots_ref])
	print("\nREFS:", [ fo.name for fo in refs])
	#print("\nLEAVES:", [ fo.name for fo in leaves])

	if arg.output:
		# Generate output config file
		if ext_functions:
			confout.add_section("library")
			for fn in ext_functions.keys():
				confout["library"][fn] = 0

		if dynamic:
			confout.add_section("dynamic")
			for fo in dynamic:
				confout["dynamic"][fo.name] = ' '

		if refs:
			confout.add_section("refs")
			for fo in refs:
				confout["refs"][fo.name] = None

		#if len(confout.options("multiple")) == 0:
		#	confout.remove_section("multiple")
		#if len(confout.options("cycle")) == 0:
		#	confout.remove_section("cycle")

		# Workaround to write file into a string variable
		class FakeFile():
			s = ""
			def write(self, a):
				self.s += a
			def insert(self, where, what):
				idx = self.s.find(where)
				if idx != -1:
					self.s = self.s[:idx] + what + '\n' + self.s[idx:]
		fake = FakeFile()
		confout.write(fake)

		# Insert comments before finally writing the file
		fake.insert("", "# File generated by stacknowledge.py to be modified by user and reused\n\n")
		fake.insert("[multiple]", "# list of funcs with multiple defs to be ignored")
		fake.insert("[cycle]", "# list of recursion calls identified and max loop count")
		fake.insert("[library]", "# list of lib calls with stack usage")
		fake.insert("[dynamic]", "# list of dynamic calls with functions called")
		fake.insert("[refs]", "# list of functions put in ptr, unused but usefull to fill dynamic section")

		with open(arg.output, 'w') as configfile:
			configfile.write(fake.s)

	return 0


if __name__ == '__main__':
	exit(stacknowledge())

