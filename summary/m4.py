"""
M4 Summary
"""
from collections import OrderedDict

import numpy as np
import pandas as pd

from common.metrics import mase, smape_2
from datasets.m4 import M4Dataset, NAIVE2_FORECAST_FILE_PATH
from summary.utils import group_values


class M4Summary:
    def __init__(self):
        self.training_set = M4Dataset.load(training=True)
        self.test_set = M4Dataset.load(training=False)

    def evaluate(self, forecast: np.ndarray):
        """
        Evaluate forecasts using M4 test dataset.

        :param forecast: Forecasts. Shape: timeseries, time.
        :return: sMAPE and OWA grouped by seasonal patterns.
        """
        forecast = np.array([v[~np.isnan(v)] for v in forecast])

        grouped_smapes = {group_name:
                              np.mean(smape_2(forecast=group_values(values=forecast,
                                                                    groups=self.test_set.groups,
                                                                    group_name=group_name),
                                              target=group_values(values=self.test_set.values,
                                                                  groups=self.test_set.groups,
                                                                  group_name=group_name)))
                          for group_name in np.unique(self.test_set.groups)}
        grouped_smapes = self.summarize_groups(grouped_smapes)

        grouped_owa = OrderedDict()

        naive2_forecasts = pd.read_csv(NAIVE2_FORECAST_FILE_PATH).values[:, 1:].astype(np.float32)
        naive2_forecasts = np.array([v[~np.isnan(v)] for v in naive2_forecasts])

        model_mases = {}
        naive2_smapes = {}
        naive2_mases = {}
        for group_name in np.unique(self.test_set.groups):
            model_forecast = group_values(forecast, self.test_set.groups, group_name)
            naive2_forecast = group_values(naive2_forecasts, self.test_set.groups, group_name)

            target = group_values(self.test_set.values, self.test_set.groups, group_name)
            # all timeseries within group have same frequency
            frequency = self.training_set.frequencies[self.test_set.groups == group_name][0]
            insample = group_values(self.training_set.values, self.test_set.groups, group_name)

            model_mases[group_name] = np.mean([mase(forecast=model_forecast[i],
                                                    insample=insample[i],
                                                    outsample=target[i],
                                                    frequency=frequency) for i in range(len(model_forecast))])
            naive2_mases[group_name] = np.mean([mase(forecast=naive2_forecast[i],
                                                     insample=insample[i],
                                                     outsample=target[i],
                                                     frequency=frequency) for i in range(len(model_forecast))])

            naive2_smapes[group_name] = np.mean(smape_2(naive2_forecast, target))
        grouped_model_mases = self.summarize_groups(model_mases)
        grouped_naive2_smapes = self.summarize_groups(naive2_smapes)
        grouped_naive2_mases = self.summarize_groups(naive2_mases)
        for k in grouped_model_mases.keys():
            grouped_owa[k] = (grouped_model_mases[k] / grouped_naive2_mases[k] +
                              grouped_smapes[k] / grouped_naive2_smapes[k]) / 2
        def round_all(d):
            return dict(map(lambda kv: (kv[0], np.round(kv[1], 3)), d.items()))
        return round_all(grouped_smapes), round_all(grouped_owa)

    def summarize_groups(self, scores):
        """
        Re-group scores respecting M4 rules.
        :param scores: Scores per group.
        :return: Grouped scores.
        """
        scores_summary = OrderedDict()

        def group_count(group_name):
            return len(np.where(self.test_set.groups == group_name)[0])

        weighted_score = {}
        for g in ['Yearly', 'Quarterly', 'Monthly']:
            weighted_score[g] = scores[g] * group_count(g)
            scores_summary[g] = scores[g]

        others_score = 0
        others_count = 0
        for g in ['Weekly', 'Daily', 'Hourly']:
            others_score += scores[g] * group_count(g)
            others_count += group_count(g)
        weighted_score['Others'] = others_score
        scores_summary['Others'] = others_score / others_count

        average = np.sum(list(weighted_score.values())) / len(self.test_set.groups)
        scores_summary['Average'] = average

        return scores_summary