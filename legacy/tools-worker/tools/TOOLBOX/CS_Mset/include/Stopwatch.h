//
// Name: Stopwatch.h
//
// Description: Implements CStopwatch class providing capabilities of an intuitive
//    stopwatch functinality.  Summary of the functions:
//
//        CStopwatch() - on creation the timer is started.
//        Reset() - resets the timer.
//        GetElapsedSeconds() - returns the seconds elpased since creation of the object or Start().
//        Stop() - stops the timer, elapsed time to that point can be read later with GetSeconds.
//        GetSeconds() - returns the number of elapsed seconds to the last Stop().
//
// Resolution:
//    The resolution of the timer is system dependent.  On Windows the resolution is no better than 1 millisecond
//    and more likely about 10 milliseconds.  On Unix/Mac the resolution is that of the clock_get_time() system call.
//    While it returns nanoseconds, resolution can be expected in the microsecond or better range on most systems.
//
// Author:  j peterson
// Copyright 2018, The Jackson Laboratory, Bar Harbor, Maine - all rights reserved
//
#ifndef STOPWATCH_H
#define STOPWATCH_H


#ifdef _WIN32
#include <windows.h>

class CStopwatch
{
public:
    CStopwatch() { m_Start = GetTickCount(); }
    ~CStopwatch() { }

    void Reset()
    {
        m_Start = GetTickCount();
    }

    void Stop()
    {
        m_End = GetTickCount();
    }

    double GetElapsedSeconds()
    {
        Stop();
        return GetSeconds();
    }

    double GetSeconds()
    {
        double fEnd = (double)m_End/1000.0;
        double fStart = (double)m_Start/1000.0;
        return (fEnd-fStart);
    }

private:
    DWORD m_Start;
    DWORD m_End;
};
#else
#include <time.h>
#include <sys/time.h>

#include <mach/clock.h>
#include <mach/mach.h>

class CStopwatch
{
public:
    CStopwatch() { host_get_clock_service(mach_host_self(), SYSTEM_CLOCK, &m_Clock); Reset(); clock_get_time(m_Clock, &m_Start); }
    ~CStopwatch() { mach_port_deallocate(mach_task_self(), m_Clock); }

    void Reset()
    {
        clock_get_time(m_Clock, &m_Start);
    }

    void Stop()
    {
        clock_get_time(m_Clock, &m_End);
    }

    double GetElapsedSeconds()
    {
        clock_get_time(m_Clock, &m_End);
        double fEnd = (double)m_End.tv_sec + (double)m_End.tv_nsec/1000000000.0;
        double fStart = (double)m_Start.tv_sec + (double)m_Start.tv_nsec/1000000000.0;
        return (fEnd-fStart);
    }

    double GetSeconds()
    {
        double fEnd = (double)m_End.tv_sec + (double)m_End.tv_nsec/1000000000.0;
        double fStart = (double)m_Start.tv_sec + (double)m_Start.tv_nsec/1000000000.0;
        return (fEnd-fStart);
    }

private:
    clock_serv_t    m_Clock;
    mach_timespec_t m_Start;
    mach_timespec_t m_End;
};
#endif

#endif // STOPWATCH_H
