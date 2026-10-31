import pandas as pd

class VariableDetector:

    @staticmethod
    def detect(df):

        results = {}

        for col in df.columns:

            series = df[col].dropna()

            if len(series) == 0:
                continue

            # Binary
            unique_values = series.nunique()

            if unique_values == 2:
                results[col] = "binary"
                continue

            # Date
            try:
                pd.to_datetime(series.iloc[:20])
                results[col] = "time_series"
                continue
            except:
                pass

            # Numeric
            if pd.api.types.is_numeric_dtype(series):

                if (series % 1 == 0).all():
                    results[col] = "discrete"
                else:
                    results[col] = "continuous"

                continue

            # Ordinal
            ordinal_words = [
                "low",
                "medium",
                "high",
                "poor",
                "good",
                "excellent"
            ]

            values = (
                series.astype(str)
                .str.lower()
                .unique()
            )

            if any(v in ordinal_words for v in values):
                results[col] = "ordinal"
            else:
                results[col] = "nominal"

        return results
