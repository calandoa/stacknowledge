

#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <errno.h>
#include <string.h>
#include <stdarg.h>


#define ESC	"\x1B["
#define TAB     ESC "40G"
#define OFF	ESC "0m"
#define BG_OFF	ESC "0;49m"
#define RED	ESC "0;31m"
#define RED2	ESC "1;31m"
#define BG_RED	ESC "0;41m"
#define GREEN	ESC "0;32m"
#define GREEN2	ESC "1;32m"
#define YELLOW	ESC "0;33m"
#define YELLOW2	ESC "1;33m"
#define BLUE	ESC "0;34m"
#define BLUE2	ESC "1;34m"
#define BG_BLUE	ESC "0;44m"
#define MAGENTA	ESC "0;35m"
#define MAGENTA2 ESC "1;35m"
#define CYAN	ESC "0;36m"
#define CYAN2	ESC "1;36m"
#define WHITE	ESC "0;37m"
#define WHITE2	ESC "1;37m"


#define MMM fprintf(stderr, "__%s__%d__\n", __FUNCTION__, __LINE__);
#define TTT fprintf(stderr, "__%s__%d__ @%08x\n", __FUNCTION__, __LINE__, NOW_MS());
#define RRR fprintf(stderr, "__%s__%d__ ->%p\n", __FUNCTION__, __LINE__, __builtin_return_address(0) );
#define DDD(x) fprintf(stderr, "__%s__%d__ %d\n", __FUNCTION__, __LINE__, (x)) ;
#define HHH(x) fprintf(stderr, "__%s__%d__ %x\n", __FUNCTION__, __LINE__, (uint32) (x)) ;


void *bsp;
void *bfa;

static void *rsp(void)
{
	register void *sp asm ("sp");
	return sp;
}

static void *rfa(void)
{
	return __builtin_frame_address(0);
}

static void aaa(char *p, int l)
{
	char xxx[20];
	for (int i = 0; i < sizeof(xxx) ; i++)
		xxx[i] = (char) i * 13;

	int sum = 0;
	for (int i = 0; i < l ; i++)
		sum += p[i] + xxx[i % sizeof(xxx)];

	printf("\t\t\taaa %d\n", sum);
	printf("\t\t\t=== %ld %ld\n", bsp - rsp(), bfa - rfa());

}

void bbb(char *p, int l)
{
	char xxx[4000];
	for (int i = 0; i < sizeof(xxx) ; i++)
		xxx[i] = (char) i * 17;

	int sum = 0;
	for (int i = 0; i < sizeof(xxx) ; i++)
		sum += p[i % l] + xxx[i];

	printf("\t\t\tbbb %d\n", sum);
	printf("\t\t\t=== %ld %ld\n", bsp - rsp(), bfa - rfa());
}

static void ccc(char *p, int l)
{
	char xxx[10000];
	for (int i = 0; i < sizeof(xxx) ; i++)
		xxx[i] = (char) i * 17;

	int sum = 0;
	for (int i = 0; i < sizeof(xxx) ; i++)
		sum += p[i % l] + xxx[i];

	printf("\t\t\tccc %d\n", sum);
	printf("\t\t\t=== %ld %ld\n", bsp - rsp(), bfa - rfa());
}

#if 1
void work(int opt)
{
	printf("\t=== %ld %ld\n", bsp - rsp(), bfa - rfa());
	//if (opt < 2)
	{
		char xxx[2000];
		for (int i = 0; i < sizeof(xxx) ; i++)
			xxx[i] = (char) i * 7;
		aaa(xxx, sizeof(xxx));
		printf("\t\t=== %ld %ld\n", bsp - rsp(), bfa - rfa());
	}

	//else
	{
		char yyy[200];
		for (int i = 0; i < sizeof(yyy) ; i++)
			yyy[i] = (char) i * 11;
		bbb(yyy, sizeof(yyy));
		printf("\t\t=== %ld %ld\n", bsp - rsp(), bfa - rfa());
	}
	printf("\t=== %ld %ld\n", bsp - rsp(), bfa - rfa());
}

#else
void work_aaa(int opt)
{
	char xxx[2000];
	for (int i = 0; i < sizeof(xxx) ; i++)
		xxx[i] = (char) i * 7;
	aaa(xxx, sizeof(xxx));
	printf("\t=== %ld %ld\n", bsp - rsp(), bfa - rfa());
}

void work_bbb(int opt)
{
	char yyy[200];
	for (int i = 0; i < sizeof(yyy) ; i++)
		yyy[i] = (char) i * 11;
	bbb(yyy, sizeof(yyy));
	printf("\t=== %ld %ld\n", bsp - rsp(), bfa - rfa());
}

void work(int opt)
{
	work_aaa(opt);

	work_bbb(opt);
}
#endif


void loop3_ext(void)
{
	char yyy[200];
	for (int i = 0; i < sizeof(yyy) ; i++)
		yyy[i] = (char) i * 11;
	ccc(yyy, sizeof(yyy));
	printf("\t=== %ld %ld\n", bsp - rsp(), bfa - rfa());
}

void loop0(int opt, char * dummy);

void loop3(int opt, char * dummy)
{
	char dummy2[10];
	loop0(opt, dummy2);

	loop3_ext();
}

void work_loop(int opt, char * dummy)
{
	printf("\t...[%d] === %ld %ld\n", opt, bsp - rsp(), bfa - rfa());

	if (opt == 0)
		return;
	loop3(opt - 1, dummy);
}

void loop2(int opt, char * dummy)
{
	char dummy2[10];
	work_loop(opt, dummy2);
}

void loop1(int opt, char * dummy)
{
	char dummy2[20];
	loop2(opt, dummy2);
}

void loop0(int opt, char * dummy)
{
	char dummy2[10];
	loop1(opt, dummy2);
}


void work_dyn(void (*paaa)(char *, int), void (*pbbb)(char *, int))
{
	printf("\t=== %ld %ld\n", bsp - rsp(), bfa - rfa());
	{
		char xxx[2000];
		for (int i = 0; i < sizeof(xxx) ; i++)
			xxx[i] = (char) i * 7;
		paaa(xxx, sizeof(xxx));
		printf("\t\t=== %ld %ld\n", bsp - rsp(), bfa - rfa());
	}

	{
		char yyy[200];
		for (int i = 0; i < sizeof(yyy) ; i++)
			yyy[i] = (char) i * 11;
		pbbb(yyy, sizeof(yyy));
		printf("\t\t=== %ld %ld\n", bsp - rsp(), bfa - rfa());
	}
	printf("\t=== %ld %ld\n", bsp - rsp(), bfa - rfa());
}

int main(int argc, char **argv)
{
	bsp = rsp();
	bfa = rfa();
	printf("--- %p %p\n", bsp, bfa);

	work(argc);

	work_dyn(&aaa, &bbb);

	loop0(3, NULL);
}
