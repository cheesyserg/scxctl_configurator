# scheduler_data.py (UPDATED)

SCHEDULER_OPTIONS = {
    "bpfland": {
        "Modes": {
            "Low Latency": {
                "Flags": "-s 5000 -S 500 -l 5000 -m performance",
                "Description": "Meant to lower latency at the cost of throughput. Suitable for soft real-time applications like Audio Processing and Multimedia."
            },
            "Power Save": {
                "Flags": "-m powersave",
                "Description": "Prioritizes power efficiency. Favors less performant cores (e.g E-cores on Intel)."
            },
            "Server": {
                "Flags": "-p",
                "Description": "Prioritize tasks with strict affinity. This option can increase throughput at the cost of latency and it is more suitable for server workloads."
            },
        },
        "Flags": {},
    },
    "flash": {
        "Modes": {
            "Low Latency": {
                "Flags": "-m performance -w -C 0",
                "Description": "Meant to lower latency at the cost of throughput. Suitable for soft real-time applications like Audio Processing and Multimedia."
            },
            "Gaming": {
                "Flags": "-m all",
                "Description": "Optimizes for high performance in games."
            },
            "Power Save": {
                "Flags": "-m powersave -I 10000 -t 10000 -s 10000 -S 1000",
                "Description": "Prioritizes power efficiency. Favor less performant cores (e.g., E-cores on Intel) and introduces a forced idle cycle every 10ms to increase power saving."
            },
            "Server": {
                "Flags": "-m all -s 20000 -S 1000 -I -1 -D -L",
                "Description": "Tuned for server workloads. Trades responsiveness for throughput."
            },
        },
        "Flags": {},
    },
    "cosmos": {
        "Modes": {
            "Auto": {
                "Flags": "-d",
                "Description": "Disables deferred wakeups. Reduces throughput and performance for certain workloads while decreasing power consumption."
            },
            "Gaming": {
                "Flags": "-c 0 -p 0",
                "Description": "Disable CPU load tracking and always enforce deadline-based scheduling to improve responsiveness."
            },
            "Power Save": {
                "Flags": "-m powersave -d -p 5000",
                "Description": "Prioritizes power efficiency. Favor less performant cores (e.g., E-cores on Intel) and disables deferred wakeups, reducing throughput while increasing power efficiency. CPU load polling increased to 5ms."
            },
            "Low Latency": {
                "Flags": "-m performance -c 0 -p 0 -w",
                "Description": "Meant to lower latency at the cost of throughput. Suitable for soft real-time applications like Audio Processing and Multimedia. Always enforce deadline-based scheduling and synchronous wake up optimizations to improve performance predictability."
            },
            "Server": {
                "Flags": "-a -s 20000",
                "Description": "Enable address space affinity to improve locality and performance in certain cache-sensitive workloads. Polling increased to 20ms."
            },
        },
        "Flags": {},
    },
    "lavd": {
        "Modes": {
            "Gaming & Low Latency": {
                "Flags": "--performance",
                "Description": "Maximizes performance by using all available cores, prioritizing physical cores."
            },
            "Power Save": {
                "Flags": "--powersave",
                "Description": "Minimizes power consumption while maintaining reasonable performance. Prioritizes efficient cores and threads over physical cores."
            },
        },
        "Flags": {},
    },
    "p2dq": {
        "Modes": {
            "Gaming": {
                "Flags": "--task-slice true -f --sched-mode performance",
                "Description": "Improves consistency in gaming performance and increases bias towards scheduling on higher performance cores."
            },
            "Low Latency": {
                "Flags": "-y -f --task-slice true",
                "Description": "Lowers latency by making interactive tasks stick more to the CPU they were assigned to and increasing the stability on slice time."
            },
            "Power Save": {
                "Flags": "--sched-mode efficiency",
                "Description": "Enhances power efficiency by prioritizing power efficient cores."
            },
            "Server": {
                "Flags": "--keep-running",
                "Description": "Improves server workloads by allowing tasks to run beyond their slice if the CPU is idle."
            },
        },
        "Flags": {},
    },
    "tickless": {
        "Modes": {
            "Gaming": {
                "Flags": "-f 5000 -s 5000",
                "Description": "Boosts gaming performance by increasing how often the scheduler detects CPU contention and triggers context switches with a shorter time slice."
            },
            "Power Save": {
                "Flags": "-f 50 -p",
                "Description": "Enhances power efficiency by lowering contention checks and aggressively trying to keep tasks on the same CPU."
            },
            "Low Latency": {
                "Flags": "-f 5000 -s 1000",
                "Description": "Similar to the gaming profile but with a further reduced slice."
            },
            "Server": {
                "Flags": "-f 100",
                "Description": "Reduced how often the scheduler checks for CPU contention to improve throughput at the cost of responsiveness."
            },
        },
        "Flags": {},
    },
    "rustland": {"Modes": {}, "Flags": {}},
    "rusty": {"Modes": {}, "Flags": {}},
    # Ensure all possible schedulers found by scxctl list are defined here
}
