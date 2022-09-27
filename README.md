# Stacknowledge
Compute stack usage from C sources and compiler output files


# Usage

-  Compile source code with gcc options `-fstack-usage` and `-fdump-final-insns`:

	```
	gcc -fstack-usage -fdump-final-insns -fno-inline example.c -o example
	```

-  Run a first pass to generate template config file. All `.gkd` files provided and corresponding `.su` will be parsed:

	```
	./stacknowledge.py -o conf.ini example.c.gkd
	```

-  Modify the config file accordingly to provide informations the parser cannot guess.

-  Run a second pass to generate template config file (`-o` changed to `-c`!):

	```
	./stacknowledge.py -c conf.ini example.c.gkd
	```

