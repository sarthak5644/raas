class AnalysisRecommender:

    RULES = {

        "nominal": [
            "frequency_table",
            "percentage_table",
            "chi_square",
            "bar_chart"
        ],

        "ordinal": [
            "median",
            "percentiles",
            "frequency_table",
            "bar_chart"
        ],

        "binary": [
            "frequency_table",
            "chi_square",
            "logistic_regression"
        ],

        "discrete": [
            "descriptive_statistics",
            "histogram",
            "boxplot"
        ],

        "continuous": [
            "descriptive_statistics",
            "summary_statistics",
            "ttest",
            "anova",
            "regression"
        ],

        "time_series": [
            "trend_analysis",
            "moving_average",
            "forecasting"
        ]
    }

    @classmethod
    def recommend(cls, variable_types):

        recommendations = set()

        for col, dtype in variable_types.items():

            methods = cls.RULES.get(dtype, [])

            for m in methods:
                recommendations.add(m)

        return list(recommendations)
