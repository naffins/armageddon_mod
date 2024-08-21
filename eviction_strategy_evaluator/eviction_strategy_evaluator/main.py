import logging
import os
import pandas as pd
import sqlite3
from . import log

logger = log.setup_custom_logger('default')

from .strategy import Strategy
from .build import Builder
from .executor import Executor
from .evaluate import evaluate_strategy_logfile

from eviction_strategy_evaluator.config import parse_device_configuration
from eviction_strategy_evaluator.config import parse_configuration

def run_strategy(number_of_measurements, eviction_counter, number_of_accesses_in_loop,
                 different_addresses_in_loop, step_size, mirroring, force, configuration, device_configuration):
    """Builds and runs an eviction strategy"""

    strategy = Strategy(configuration, device_configuration,
                        eviction_counter,
                        number_of_accesses_in_loop,
                        different_addresses_in_loop,
                        step_size,
                        mirroring)
    
    if os.path.exists(strategy.get_logfile_name()):
        logger.info("Skiping evaluation of %s: evaluation done already", strategy.get_name())
        return strategy

    logger.info("Evaluating %s", strategy.get_name())

    strategy.build(force)
    strategy.run(number_of_measurements, force)

    return strategy

def cmd_run_strategy(number_of_measurements, eviction_counter, number_of_accesses_in_loop,
                 different_addresses_in_loop, step_size, mirroring, force, configuration_file, device_configuration_file):
    device_configuration = parse_device_configuration(device_configuration_file)

    strategy = run_strategy(number_of_measurements, eviction_counter, number_of_accesses_in_loop,
                 different_addresses_in_loop, step_size, mirroring, force, parse_configuration(configuration_file),
                 device_configuration)

    logfile = strategy.get_logfile_name()

    # read log file
    result = evaluate_strategy_logfile(logfile, device_configuration, device_configuration['device']['threshold'])
    if result:
        logger.info("Eviction rate: %f%%", result['rate'])
        logger.info("Average runtime: %f", result['average_runtime'])

def cmd_run_strategies(number_of_measurements, max_eviction_counter, max_number_of_accesses_in_loop,
                 max_different_addresses_in_loop, max_step_size, with_mirroring, force, configuration_file, device_configuration_file):
    # Generate all strategies and test them

    configuration = parse_configuration(configuration_file)
    device_configuration = parse_device_configuration(device_configuration_file)

    for a_i in range(max_number_of_accesses_in_loop, 0, -1):
        for d_i in range(max_different_addresses_in_loop, 0, -1):
            for s_i in range(max_step_size, 0, -1):
                if d_i < s_i:
                    continue

                for e_i in range(max_eviction_counter, 0, -1):
                    number_of_addresses = e_i + d_i - 1
                    if (number_of_addresses >= d_i):
                        run_strategy(number_of_measurements, e_i, a_i, d_i, s_i, False, force, configuration, device_configuration)

                        if with_mirroring is True:
                            run_strategy(number_of_measurements, e_i, a_i, d_i, s_i, True, force, configuration, device_configuration)

def cmd_evaluate_strategy(logfile, threshold, device_configuration_file):
    device_configuration = parse_device_configuration(device_configuration_file)

    # read log file
    result = evaluate_strategy_logfile(logfile, device_configuration, threshold)

    logger.info("Eviction rate: %f%%", result['rate'])
    logger.info("Average runtime: %f", result['average_runtime'])

def cmd_evaluate_strategies(logfile_directory, threshold, device_configuration_file):
    device_configuration = parse_device_configuration(device_configuration_file)

    results = []
    for f in sorted(os.listdir(logfile_directory)):
        if not f.endswith(".log"):
            continue

        logfile = os.path.join(logfile_directory, f)

        # read log file
        result = evaluate_strategy_logfile(logfile, device_configuration, threshold)
        if result is not None:
            results.append(result['raw'])

    df = pd.DataFrame(results, columns=['Strategy', 'Number of addresses', 'Number of accesses in loop', 'Different addresses in loop',
                                          'Step size', 'Mirrored', 'Rate', 'Average runtime'])
    df = df.sort_values(['Strategy'])

    df.to_csv('strategies.csv')

    conn = sqlite3.connect('strategies.db')
    df.to_sql('strategies', conn, if_exists="replace")
