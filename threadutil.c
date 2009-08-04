/*
** $Id: threadutil.c,v 1.21 2009-08-04 22:16:54 rosinski Exp $
**
** Author: Jim Rosinski
** 
** Utility functions handle thread-based GPTL needs.
*/

#include <stdlib.h>
#include <stdio.h>

#include "private.h"

/* Max allowable number of threads */
#define MAX_THREADS 128

/* VERBOSE is a debugging ifdef local to this file */
#undef VERBOSE

#if ( defined THREADED_OMP )

#include <omp.h>

/* array of thread ids used to determine if thread has been started */
static int *threadid_omp;  

/*
** threadinit: Initialize locking capability and set number of threads
**
** Output arguments:
**   nthreads:   number of threads
**   maxthreads: number of threads (these don't differ under OpenMP)
*/

int threadinit (int *nthreads, int *maxthreads)
{
  int t;  /* loop index */

  *maxthreads = omp_get_max_threads ();
  *nthreads = 0;

  if (omp_get_thread_num () > 0)
    return GPTLerror ("GPTL: threadinit: MUST be called only by master thread");

  threadid_omp = GPTLallocate (*maxthreads * sizeof (int));
  for (t = 0; t < *maxthreads; ++t)
    threadid_omp[t] = -1;

#ifdef VERBOSE
  printf ("OMP threadinit: Set *maxthreads=%d *nthreads=%d\n", *maxthreads, *nthreads);
#endif
  
  return 0;
}

/*
** threadfinalize: no-op under OpenMP
*/

void threadfinalize ()
{
}

/*
** get_thread_num: determine thread number of the calling thread
**
** Input args:
**   nthreads:   number of threads
**   maxthreads: number of threads (unused in OpenMP case)
**
** Return value: thread number (success) or GPTLerror (failure)
*/

int get_thread_num (int *nthreads, int *maxthreads)
{
  int t;       /* thread number */

  if ((t = omp_get_thread_num ()) >= *maxthreads)
    return GPTLerror ("get_thread_num: returned id=%d exceeds maxthreads=%d\n",
		      t, *maxthreads);

  /*
  ** The following test is true only once for each thread, so no need to worry
  ** about false cache sharing
  */

  if (threadid_omp[t] == -1) {
    threadid_omp[t] = t;

#ifdef VERBOSE
    printf ("OMP get_thread_num: 1st call t=%d\n", t);
#endif

#ifdef HAVE_PAPI
  /*
  ** When HAVE_PAPI is true, need to create and start an event set for the new thread.
  */

    if (GPTLget_npapievents () > 0) {
#ifdef VERBOSE
      printf ("OMP get_thread_num: Starting EventSet t=%d\n", t);
#endif
      if (GPTLcreate_and_start_events (t) < 0)
	return GPTLerror ("get_thread_num: error from GPTLcreate_and_start_events for thread %d\n",
			  t);
    }
#endif

    *nthreads = *maxthreads;
  }
  return t;
}

void print_threadmapping (int nthreads, FILE *fp)
{
  int n;

  fprintf (fp, "\n");
  fprintf (fp, "Thread mapping:\n");
  for (n = 0; n < nthreads; ++n)
    fprintf (fp, "threadid_omp[%d]=%d\n", n, threadid_omp[n]);
}

#elif ( defined THREADED_PTHREADS )

#include <pthread.h>

static int lock_mutex (void);      /* lock a mutex for entry into a critical region */
static int unlock_mutex (void);    /* unlock a mutex for exit from a critical region */

static pthread_mutex_t t_mutex = PTHREAD_MUTEX_INITIALIZER;
static pthread_t *threadid;

/*
** threadinit: Set number of threads and max number of threads
**
** Output arguments:
**   nthreads:   number of threads
**   maxthreads: number of threads (these don't differ under OpenMP)
**
** Return value: 0 (success) or GPTLerror (failure)
*/

int threadinit (int *nthreads, int *maxthreads)
{
  int nbytes;
  int rc;
  int t;

  /* Manage the threadid array which maps physical thread IDs to logical IDs */

  nbytes = MAX_THREADS * sizeof (pthread_t);
  if ( ! (threadid = (pthread_t *) malloc (nbytes)))
    return GPTLerror ("threadinit: malloc failure for %d items\n", MAX_THREADS);

  /*
  ** Initialize nthreads to 0 and define the threadid array now that initialization 
  ** is done. The actual value will be determined as get_thread_num is called.
  */

  *nthreads = 0;
  *maxthreads = MAX_THREADS;

  for (t = 0; t < *maxthreads; ++t)
    threadid[t] = (pthread_t) -1;

#ifdef VERBOSE
  printf ("PTHREADS threadinit: Set *maxthreads=%d *nthreads=%d\n", *maxthreads, *nthreads);
#endif

  return 0;
}

/*
** threadfinalize: free allocated space
*/

void threadfinalize ()
{
  free (threadid);
}

/*
** get_thread_num: determine zero-based thread number of the calling thread.
**                 Also: update nthreads and maxthreads if necessary.
**
** Input/output args:
**   nthreads:   number of threads
**   maxthreads: max number of threads
**
** Return value: thread number (success) or GPTLerror (failure)
*/

int get_thread_num (int *nthreads, int *maxthreads)
{
  int n;                 /* return value: loop index over number of threads */
  pthread_t mythreadid;  /* thread id from pthreads library */

  mythreadid = pthread_self ();

  if (lock_mutex () < 0)
    return GPTLerror ("get_thread_num: mutex lock failure\n");

  /*
  ** Loop over known physical thread IDs.  When my id is found, map it 
  ** to logical thread id for indexing.  If not found return a negative 
  ** number.
  ** A critical region is necessary because acess to
  ** the array threadid must be by only one thread at a time.
  */

  for (n = 0; n < *nthreads; ++n)
    if (pthread_equal (mythreadid, threadid[n]))
      break;

  /*
  ** If our thread id is not in the known list, add to it after checking that
  ** we do not have too many threads.
  */

  if (n == *nthreads) {
    if (*nthreads >= MAX_THREADS) {
      if (unlock_mutex () < 0)
	fprintf (stderr, "get_thread_num: mutex unlock failure\n");

      return GPTLerror ("get_thread_num: nthreads=%d is too big Recompile "
			"with larger value of MAX_THREADS\n", *nthreads);
    }    

    threadid[n] = mythreadid;

#ifdef VERBOSE
    printf ("PTHREADS get_thread_num: 1st call threadid=%lu maps to location %d\n", (unsigned long) mythreadid, n);
#endif

#ifdef HAVE_PAPI

    /*
    ** When HAVE_PAPI is true, need to create and start an event set for the new thread
    */

    if (GPTLget_npapievents () > 0) {
#ifdef VERBOSE
      printf ("PTHREADS get_thread_num: Starting EventSet threadid=%lu location=%d\n", (unsigned long) mythreadid, n);
#endif
      if (GPTLcreate_and_start_events (n) < 0)
	return GPTLerror ("get_thread_num: error from GPTLcreate_and_start_events for thread %d\n",
			  n);
    }
#endif

    ++*nthreads;
#ifdef VERBOSE
    printf ("PTHREADS get_thread_num: *nthreads=%d\n", *nthreads);
#endif
  }
    
  if (unlock_mutex () < 0)
    return GPTLerror ("get_thread_num: mutex unlock failure\n");

  return n;
}

/*
** lock_mutex: lock a mutex for private access
*/

static int lock_mutex ()
{
  if (pthread_mutex_lock (&t_mutex) != 0)
    return GPTLerror ("pthread_lock_mutex failure\n");
  return 0;
}

/*
** unlock_mutex: unlock a mutex from private access
*/

static int unlock_mutex ()
{
  if (pthread_mutex_unlock (&t_mutex) != 0)
    return GPTLerror ("pthread_unlock_mutex failure\n");
  return 0;
}

void print_threadmapping (int nthreads, FILE *fp)
{
  int n;

  fprintf (fp, "\n");
  fprintf (fp, "Thread mapping:\n");
  for (n = 0; n < nthreads; ++n)
    fprintf (fp, "threadid[%d]=%d\n", n, (int) threadid[n]);
}

#else

/*
** Unthreaded case
*/

static int threadid = -1;

int threadinit (int *nthreads, int *maxthreads)
{
  *nthreads = 0;
  *maxthreads = 1;
  return 0;
}

void threadfinalize ()
{
}

int get_thread_num (int *nthreads, int *maxthreads)
{
  /*
  ** When HAVE_PAPI is true, need to create and start an event set
  ** for the new thread
  */

#ifdef HAVE_PAPI
  if (threadid == -1 && GPTLget_npapievents () > 0) {
    if (GPTLcreate_and_start_events (0) < 0)
      return GPTLerror ("get_thread_num: error from GPTLcreate_and_start_events for thread %0\n");

    threadid = 0;
  }
#endif

  return 0;
}

void print_threadmapping (int nthreads, FILE *fp)
{
  int n;

  fprintf (fp, "\n");
  fprintf (fp, "Thread mapping: no thread map for unthreaded case\n");
}

#endif
