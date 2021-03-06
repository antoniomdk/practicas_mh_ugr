from algorithms.evolutionary import EvolutionaryAlgorithm, MemeticAlgorithm
from algorithms.local_search import LocalSearch
from algorithms.relief import Relief

import matplotlib.pyplot as plt
import os
import timeit
import argparse

from joblib import Parallel, delayed, cpu_count
from sklearn.preprocessing import minmax_scale, FunctionTransformer, LabelEncoder
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import accuracy_score
from sklearn.neighbors import KNeighborsClassifier

import pandas as pd
import numpy as np
import matplotlib

matplotlib.use('Agg')

KNN = FunctionTransformer(lambda x: x, validate=False)
KNN.reduction = 0

ALGORITHMS = {
    'knn':
    KNN,
    'relief':
    Relief(),
    'local-search':
    LocalSearch(),
    'agg-blx':
    EvolutionaryAlgorithm(mate='blx', generational=True),
    'agg-ca':
    EvolutionaryAlgorithm(mate='ca', generational=True),
    'age-blx':
    EvolutionaryAlgorithm(mate='blx', generational=False, cxprob=1),
    'age-ca':
    EvolutionaryAlgorithm(mate='ca', generational=False, cxprob=1),
    'AM-(1,1.0)':
    MemeticAlgorithm(
        population_size=10,
        mate='blx',
        generational=True,
        strategy='AM-(1,1.0)'),
    'AM-(1,0.1)':
    MemeticAlgorithm(
        population_size=10,
        mate='blx',
        generational=True,
        strategy='AM-(1,0.1)'),
    'AM-(1,0.1mej)':
    MemeticAlgorithm(
        population_size=10,
        mate='blx',
        generational=True,
        strategy='AM-(1,0.1mej)')
}


def evaluate_partition(X_train, y_train, X_test, y_test, transformer,
                       make_trace):
    # Beginning of timing zone
    t_start = timeit.default_timer()
    transformer.fit(X_train, y_train)
    X_train = transformer.transform(X_train)
    X_test = transformer.transform(X_test)
    knn = KNeighborsClassifier(n_neighbors=1)
    knn.fit(X_train, y_train)
    # End of timing zone
    t_stop = timeit.default_timer()
    # Gathering information
    accuracy = accuracy_score(knn.predict(X_test), y_test)
    time = t_stop - t_start
    reduction = transformer.reduction
    if make_trace:
        result = (accuracy, time, reduction, transformer.trace)
    else:
        result = (accuracy, time, reduction)
    return result


def pipeline(X, y, transformer, seed, make_trace, n_jobs=4):
    X = minmax_scale(X)
    kfold = StratifiedKFold(5, shuffle=True, random_state=seed)
    results = Parallel(n_jobs=n_jobs)(delayed(evaluate_partition)(
        X[train], y[train], X[test], y[test], transformer, make_trace)
        for train, test in kfold.split(X, y))
    if len(results[0]) > 3:
        accuracies, times, reductions, traces = zip(*results)
    else:
        accuracies, times, reductions = zip(*results)
        traces = []
    return np.array(accuracies), np.array(times), np.array(reductions), traces


def create_dataframe(accuracies, times, reductions):
    columns = ['Accuracy', 'Reduction', 'Aggregation', 'Time']
    index = ['Partition ' + str(i + 1) for i in range(5)]
    agreggations = (accuracies + reductions) / 2
    data = np.array([accuracies, reductions, agreggations, times]).T
    return pd.DataFrame(data=data, columns=columns, index=index)


def evaluate_algorithm(algorithm, X, Y, seed, make_trace, n_jobs):
    transformer = ALGORITHMS[algorithm]
    transformer.seed = seed
    if algorithm == 'relief' or algorithm == 'knn':
        make_trace = False
    results = pipeline(X, Y, transformer, seed, make_trace, n_jobs)
    return create_dataframe(*results[:-1]), results[-1]


def pretty_print(dataset, algorithm, seed, results):
    summary = results.describe().loc[['mean', 'std', '50%']]
    summary.index = ['Mean', 'Std.Dev', 'Median']
    output = """
=======================================================
    %s     |     %s      |  SEED = %d
=======================================================\n%s\n\n%s
    """ % (dataset.upper(), algorithm.upper(), seed, results.to_string(),
           summary)
    return output


def generate_graphics(algorithm, filename, results, traces):
    """Generates some bloxplots based on the parameter *results*
    and save it on a file. Optionally, it creates a trace line plot.
    """
    _, axes = plt.subplots(2, len(results.columns) // 2, figsize=(10, 6))
    plt.suptitle('Algorithm Results', fontsize='x-large')
    for col, axis in zip(results.columns, axes.flatten()):
        results.boxplot(column=col, ax=axis)
    plt.savefig('%s_results.png' % filename)
    plt.clf()
    if traces:
        plt.title(algorithm + ' fitness function trace')
        for i, t in enumerate(traces):
            plt.plot(t, label='Partition %d' % (i + 1))
        plt.legend()
        plt.savefig('%s_trace.png' % filename)


def create_directory(path):
    """Creates a directory if it doesn't exist."""
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)


def load_dataset(dataset):
    df = None
    if dataset in DATASETS:
        df = pd.read_csv('../BIN/%s.csv' % dataset)
    elif dataset.endswith('.csv'):
        df = pd.read_csv(dataset)
    X = df.iloc[:, :-1].values
    y = df.iloc[:, -1].values
    y = LabelEncoder().fit_transform(y)
    return X, y


def get_filename(filepath):
    base = os.path.basename(filepath)
    return os.path.splitext(base)[0]


def main(dataset, algorithm, seed, trace, n_jobs, to_excel):
    X, y = load_dataset(dataset)
    dataset = get_filename(dataset)
    results, traces = evaluate_algorithm(algorithm, X, y, seed, trace, n_jobs)
    filename = 'output/%s/%s_%s' % (algorithm, dataset, seed)
    create_directory('output/%s/' % algorithm)
    generate_graphics(algorithm, filename, results, traces)
    output = pretty_print(dataset, algorithm, seed, results)
    if to_excel:
        results.to_excel(filename + '.xlsx')
    print(output)


DATASETS = ['colposcopy', 'texture', 'ionosphere']
N_JOBS_RANGE = list(range(1, min(4, cpu_count()) + 1))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        'dataset', type=str, help='Predefined datasets or a csv file')
    parser.add_argument(
        'algorithm',
        type=str,
        choices=ALGORITHMS.keys(),
        help='Algorithm to use for feature weighting')
    parser.add_argument(
        '--seed',
        type=int,
        default=77766814,
        help='Seed to initialize the random generator')
    parser.add_argument(
        '--n_jobs',
        type=int,
        choices=N_JOBS_RANGE,
        default=1,
        help='Number of jobs to run in parallel to evaluate partitions.')
    parser.add_argument(
        '--trace', help='Generate trace for local search', action='store_true')
    parser.add_argument(
        '--to_excel', help='Dump results into xlsx file', action='store_true')
    args = vars(parser.parse_args())
    main(**args)
