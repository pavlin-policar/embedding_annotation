import unittest

import numpy as np
import pandas as pd

import veca.rules
import veca.variables
import veca.preprocessing as pp


class TestIngest(unittest.TestCase):
    def setUp(self) -> None:
        df = pd.DataFrame()
        df["cont1"] = [5, 2, 3, 1, 5]
        df["cont2"] = [2.1, 5.2, 5.1, 5.2, 2.0]
        df["disc1"] = pd.Categorical([0, 0, 1, 0, 1])
        df["disc2"] = pd.Categorical(["r", "g", "b", "r", "b"])
        df["disc3"] = pd.Categorical(
            ["low", "low", "high", "med", "high"],
            categories=["low", "med", "high"],
            ordered=True,
        )
        self.df = df

    def test_ingest_with_raw_dataframe(self):
        result = data.ingest(self.df)
        self.assertTrue(all(isinstance(c, veca.data.variable.Variable) for c in result.columns))
        self.assertTrue(all(isinstance(c.name, str) for c in result.columns))

    def test_ingest_with_mixed_types_dataframe(self):
        df = pd.DataFrame()
        df["cont1"] = [5, 2, 3, 1, 5]
        v = veca.data.variable.ContinuousVariable("cont2")
        df[v] = [2.1, 5.2, 5.1, 5.2, 2.0]
        df["disc1"] = pd.Categorical([0, 0, 1, 0, 1])
        v = veca.data.variable.DiscreteVariable("disc2", categories=["r", "g", "b"])
        df[v] = pd.Categorical(["r", "g", "b", "r", "b"])
        df["disc3"] = pd.Categorical(
            ["low", "low", "high", "med", "high"],
            categories=["low", "med", "high"],
            ordered=True,
        )

        result = data.ingest(df)
        self.assertTrue(all(isinstance(c, veca.data.variable.Variable) for c in result.columns))
        self.assertTrue(all(isinstance(c.name, str) for c in result.columns))

    def test_already_ingested_dataframe_does_nothing(self):
        ingested = data.ingest(self.df)
        result = data.ingest(ingested)
        self.assertTrue(all(isinstance(c, veca.data.variable.Variable) for c in result.columns))
        self.assertTrue(all(isinstance(c.name, str) for c in result.columns))


class TestIngestedToPandas(unittest.TestCase):
    def setUp(self) -> None:
        df = pd.DataFrame()
        df["cont1"] = [5, 2, 3, 1, 5]
        df["cont2"] = [2.1, 5.2, 5.1, 5.2, 2.0]
        df["disc1"] = pd.Categorical([0, 0, 1, 0, 1])
        df["disc2"] = pd.Categorical(["r", "g", "b", "r", "b"])
        df["disc3"] = pd.Categorical(
            ["low", "low", "high", "med", "high"],
            categories=["low", "med", "high"],
            ordered=True,
        )
        self.df = df
        self.df_ingested = data.ingest(df)

    def test_ingested_to_pandas(self):
        reverted = data.ingested_to_pandas(self.df_ingested)
        self.assertTrue(self.df.equals(reverted))


class TestDiscretize(unittest.TestCase):
    def setUp(self) -> None:
        df = pd.DataFrame()
        df["cont1"] = [5, 2, 3, 1, 5]
        df["cont2"] = [2.1, 5.2, 5.1, 5.2, 2.0]
        df["disc1"] = pd.Categorical([0, 0, 1, 0, 1])
        df["disc2"] = pd.Categorical(["r", "g", "b", "r", "b"])
        df["disc3"] = pd.Categorical(
            ["low", "low", "high", "med", "high"],
            categories=["low", "med", "high"],
            ordered=True,
        )
        self.df = df

    def test_discretization_with_no_continuous_columns(self):
        df = self.df[["disc1", "disc2", "disc3"]]
        df_discretized = pp._discretize(df)
        self.assertEqual(df.shape, df_discretized.shape)

    def test_discretization_retains_number_of_samples(self):
        df_discretized = pp._discretize(self.df)
        self.assertEqual(
            self.df.shape[0],
            df_discretized.shape[0],
            "Discretization changed number of instances!",
        )

    def test_discretize_mixed_variable_types(self):
        df_discretized = pp._discretize(self.df)
        self.assertFalse(
            any(isinstance(c, veca.data.variable.ContinuousVariable) for c in df_discretized.columns),
            "Discretized dataframe contains continuous variables!",
        )

        self.assertTrue(
            any(
                isinstance(c, veca.data.variable.DerivedVariable) for c in df_discretized.columns
            ),
            "Discretized dataframe contains no explanatory variables!",
        )

    def test_discretization_on_only_continuous_variables(self):
        df_discretized = pp._discretize(self.df[["cont1", "cont2"]])
        self.assertTrue(
            all(
                isinstance(c, veca.data.variable.DerivedVariable) for c in df_discretized.columns
            ),
            "Discretized dataframe should contain only explanatory variables!",
        )


class TestOneHotEncoding(unittest.TestCase):
    def setUp(self) -> None:
        df = pd.DataFrame()
        df["cont1"] = [5, 2, 3, 1, 5]
        df["cont2"] = [2.1, 5.2, 5.1, 5.2, 2.0]
        df["disc1"] = pd.Categorical([0, 0, 1, 0, 1])
        df["disc2"] = pd.Categorical(["r", "g", "b", "r", "b"])
        df["disc3"] = pd.Categorical(
            ["low", "low", "high", "med", "high"],
            categories=["low", "med", "high"],
            ordered=True,
        )
        self.df = df

    def test_one_hot_encoding_with_no_discrete_columns(self):
        df = self.df[["cont1", "cont2"]]
        df_continuized = pp._one_hot(df)
        self.assertEqual(df.shape, df_continuized.shape)

    def test_one_hot_encoding_retains_number_of_samples(self):
        df_one_hot = pp._one_hot(self.df)
        self.assertEqual(
            self.df.shape[0],
            df_one_hot.shape[0],
            "One-hot encoding changed number of instances!",
        )

    def test_one_hot_encoding_on_only_categorical_variables(self):
        df_encoded = pp._one_hot(self.df[["disc1"]])
        self.assertEqual(df_encoded.shape[1], 2)

        df_encoded = pp._one_hot(self.df[["disc2"]])
        self.assertEqual(df_encoded.shape[1], 3)

        df_encoded = pp._one_hot(self.df[["disc3"]])
        self.assertEqual(df_encoded.shape[1], 3)

        df_encoded = pp._one_hot(self.df[["disc1", "disc2", "disc3"]])
        self.assertEqual(df_encoded.shape[1], 8)

        self.assertTrue(
            all(isinstance(c, veca.data.variable.DerivedVariable) for c in df_encoded.columns),
            "Encoded dataframe should contain only explanatory variables!",
        )

    def test_one_hot_encoding_on_mixed_type(self):
        df_encoded = pp._one_hot(self.df)
        self.assertEqual(df_encoded.shape[1], 10)

        self.assertFalse(
            any(type(c) is veca.data.variable.DiscreteVariable for c in df_encoded.columns),
            "Encoded dataframe contains discrete variables!",
        )

        self.assertTrue(
            any(isinstance(c, veca.data.variable.DerivedVariable) for c in df_encoded.columns),
            "Encoded dataframe contains no explanatory variables!",
        )

    def test_one_hot_encoding_with_no_discrete_variables(self):
        df = data.ingest(self.df[["cont1", "cont2"]])
        df_encoded = pp._one_hot(df)
        self.assertTrue(df.equals(df_encoded))

        df = pp._discretize(data.ingest(self.df[["cont1", "cont2"]]))
        df_encoded = pp._one_hot(df)
        self.assertTrue(df.equals(df_encoded))


class TestIntervalRule(unittest.TestCase):
    def test_can_merge_with_non_interval_rules(self):
        r1 = veca.rules.IntervalRule(0, 5)
        r2 = veca.rules.EqualityRule(5)

        self.assertFalse(r1.can_merge_with(r2))
        self.assertFalse(r2.can_merge_with(r1))

    def test_can_merge_with_other_discretized_interval_rules(self):
        r1 = veca.rules.IntervalRule(0, 5)
        r2 = veca.rules.IntervalRule(5, 10)
        r3 = veca.rules.IntervalRule(10, 15)

        self.assertTrue(r1.can_merge_with(r2))
        self.assertTrue(r2.can_merge_with(r1))
        self.assertTrue(r2.can_merge_with(r3))
        self.assertTrue(r3.can_merge_with(r2))
        self.assertFalse(r1.can_merge_with(r3))
        self.assertFalse(r3.can_merge_with(r1))

    def test_can_merge_with_overlapping_interval_rules(self):
        r1 = veca.rules.IntervalRule(0, 6)
        r2 = veca.rules.IntervalRule(4, 10)
        r3 = veca.rules.IntervalRule(9, 15)
        r4 = veca.rules.IntervalRule(1, 4)

        self.assertTrue(r1.can_merge_with(r2))
        self.assertTrue(r2.can_merge_with(r1))
        self.assertTrue(r2.can_merge_with(r3))
        self.assertTrue(r3.can_merge_with(r2))
        # One contained within the other
        self.assertTrue(r1.can_merge_with(r4))
        self.assertTrue(r4.can_merge_with(r1))
        # Disjoint
        self.assertFalse(r1.can_merge_with(r3))
        self.assertFalse(r3.can_merge_with(r1))

    def test_can_merge_with_open_intervals(self):
        r1 = veca.rules.IntervalRule(upper=6)
        r2 = veca.rules.IntervalRule(lower=5, upper=10)
        r3 = veca.rules.IntervalRule(lower=9)

        self.assertTrue(r1.can_merge_with(r1))
        self.assertTrue(r2.can_merge_with(r2))
        self.assertTrue(r3.can_merge_with(r3))

        self.assertTrue(r1.can_merge_with(r2))
        self.assertTrue(r2.can_merge_with(r1))
        self.assertTrue(r2.can_merge_with(r3))
        self.assertTrue(r3.can_merge_with(r2))
        self.assertFalse(r1.can_merge_with(r3))
        self.assertFalse(r3.can_merge_with(r1))

    def test_merge_with_non_interval_rule(self):
        r1 = veca.rules.IntervalRule(0, 5)
        r2 = veca.rules.EqualityRule(5)

        with self.assertRaises(veca.rules.IncompatibleRuleError):
            r1.merge_with(r2)
        with self.assertRaises(veca.rules.IncompatibleRuleError):
            r2.merge_with(r1)

    def test_merge_with_other_discretized_interval_rules(self):
        r1 = veca.rules.IntervalRule(0, 5)
        r2 = veca.rules.IntervalRule(5, 10)
        r3 = veca.rules.IntervalRule(10, 15)

        self.assertEqual(r1.merge_with(r1), r1)

        self.assertEqual(r1.merge_with(r2), veca.rules.IntervalRule(0, 10))
        self.assertEqual(r2.merge_with(r1), veca.rules.IntervalRule(0, 10))

        self.assertEqual(r2.merge_with(r3), veca.rules.IntervalRule(5, 15))
        self.assertEqual(r3.merge_with(r2), veca.rules.IntervalRule(5, 15))

        with self.assertRaises(veca.rules.IncompatibleRuleError):
            r1.merge_with(r3)
        with self.assertRaises(veca.rules.IncompatibleRuleError):
            r3.merge_with(r1)

    def test_merge_with_overlapping_interval_rules(self):
        r1 = veca.rules.IntervalRule(0, 6)
        r2 = veca.rules.IntervalRule(4, 10)
        r3 = veca.rules.IntervalRule(9, 15)
        r4 = veca.rules.IntervalRule(1, 4)

        self.assertEqual(r1.merge_with(r2), veca.rules.IntervalRule(0, 10))
        self.assertEqual(r2.merge_with(r1), veca.rules.IntervalRule(0, 10))

        self.assertEqual(r2.merge_with(r3), veca.rules.IntervalRule(4, 15))
        self.assertEqual(r3.merge_with(r2), veca.rules.IntervalRule(4, 15))

        # One contained within the other
        self.assertEqual(r1.merge_with(r4), veca.rules.IntervalRule(0, 6))
        self.assertEqual(r4.merge_with(r1), veca.rules.IntervalRule(0, 6))

        # Disjoint
        with self.assertRaises(veca.rules.IncompatibleRuleError):
            r1.merge_with(r3)
        with self.assertRaises(veca.rules.IncompatibleRuleError):
            r3.merge_with(r1)

    def test_merge_open_intervals(self):
        r1 = veca.rules.IntervalRule(upper=6)
        r2 = veca.rules.IntervalRule(lower=5, upper=10)
        r3 = veca.rules.IntervalRule(lower=9)

        self.assertEqual(r1.merge_with(r1), r1)
        self.assertEqual(r2.merge_with(r2), r2)
        self.assertEqual(r3.merge_with(r3), r3)

        self.assertEqual(r1.merge_with(r2), veca.rules.IntervalRule(upper=10))
        self.assertEqual(r2.merge_with(r1), veca.rules.IntervalRule(upper=10))

        self.assertEqual(r2.merge_with(r3), veca.rules.IntervalRule(lower=5))
        self.assertEqual(r3.merge_with(r2), veca.rules.IntervalRule(lower=5))

        with self.assertRaises(veca.rules.IncompatibleRuleError):
            r1.merge_with(r3)
        with self.assertRaises(veca.rules.IncompatibleRuleError):
            r3.merge_with(r1)

    def test_contains_non_interval_rule(self):
        r1 = veca.rules.IntervalRule(0, 5)
        r2 = veca.rules.EqualityRule(5)
        r3 = veca.rules.OneOfRule({1, 2, 3})

        self.assertFalse(r1.contains(r2))
        self.assertFalse(r1.contains(r3))

    def test_contains(self):
        r1 = veca.rules.IntervalRule(lower=5, upper=10)
        r2 = veca.rules.IntervalRule(lower=7, upper=8)
        self.assertTrue(r1.contains(r1))

        self.assertTrue(r1.contains(r2))
        self.assertFalse(r2.contains(r1))

        r1 = veca.rules.IntervalRule(lower=5, upper=10)
        r2 = veca.rules.IntervalRule(upper=6)
        r3 = veca.rules.IntervalRule(lower=9)
        self.assertFalse(r1.contains(r2))
        self.assertFalse(r1.contains(r3))
        self.assertFalse(r2.contains(r1))
        self.assertFalse(r3.contains(r1))

        r1 = veca.rules.IntervalRule(lower=5, upper=10)
        r2 = veca.rules.IntervalRule(lower=-50)
        r3 = veca.rules.IntervalRule(upper=50)
        self.assertTrue(r2.contains(r1))
        self.assertTrue(r3.contains(r1))
        self.assertFalse(r1.contains(r2))
        self.assertFalse(r1.contains(r3))


class TestEqualityRule(unittest.TestCase):
    def test_can_merge_with_other_rules(self):
        r1 = veca.rules.EqualityRule(5)
        r2 = veca.rules.IntervalRule(0, 5)
        r3 = veca.rules.OneOfRule({1, 2})
        r4 = veca.rules.EqualityRule(6)

        self.assertTrue(r1.can_merge_with(r1))

        self.assertFalse(r1.can_merge_with(r2))
        self.assertFalse(r2.can_merge_with(r1))

        self.assertTrue(r1.can_merge_with(r3))
        self.assertTrue(r3.can_merge_with(r1))

        self.assertTrue(r1.can_merge_with(r4))
        self.assertTrue(r4.can_merge_with(r1))

    def test_merge_with_incompatible_rules(self):
        r1 = veca.rules.EqualityRule(5)
        r2 = veca.rules.IntervalRule(0, 5)

        with self.assertRaises(veca.rules.IncompatibleRuleError):
            r1.merge_with(r2)
        with self.assertRaises(veca.rules.IncompatibleRuleError):
            r2.merge_with(r1)

    def test_merge_with_other_equality_rule(self):
        r1 = veca.rules.EqualityRule(3)
        r2 = veca.rules.EqualityRule(5)

        self.assertEqual(r1.merge_with(r2), veca.rules.OneOfRule({3, 5}))
        self.assertEqual(r2.merge_with(r1), veca.rules.OneOfRule({3, 5}))

    def test_contains_non_equality_rule(self):
        r1 = veca.rules.EqualityRule(5)
        r2 = veca.rules.IntervalRule(0, 5)
        r3 = veca.rules.OneOfRule({1, 2, 3})

        self.assertFalse(r1.contains(r2))
        self.assertFalse(r1.contains(r3))

    def test_contains(self):
        r1 = veca.rules.EqualityRule(5)
        r2 = veca.rules.EqualityRule(5)
        r3 = veca.rules.EqualityRule(2)

        self.assertTrue(r1.contains(r1))
        self.assertTrue(r1.contains(r2))
        self.assertTrue(r2.contains(r1))
        self.assertFalse(r1.contains(r3))
        self.assertFalse(r3.contains(r1))


class TestOneOfRule(unittest.TestCase):
    def test_can_merge_with_other_rules(self):
        r1 = veca.rules.OneOfRule({1, 2})
        r2 = veca.rules.IntervalRule(0, 5)
        r3 = veca.rules.EqualityRule(5)
        r4 = veca.rules.EqualityRule({2, 3})

        self.assertTrue(r1.can_merge_with(r1))

        self.assertFalse(r1.can_merge_with(r2))
        self.assertFalse(r2.can_merge_with(r1))

        self.assertTrue(r1.can_merge_with(r3))
        self.assertTrue(r3.can_merge_with(r1))

        self.assertTrue(r1.can_merge_with(r4))
        self.assertTrue(r4.can_merge_with(r1))

    def test_merge_with_incompatible_rules(self):
        r1 = veca.rules.OneOfRule({1, 2})
        r2 = veca.rules.IntervalRule(0, 5)

        with self.assertRaises(veca.rules.IncompatibleRuleError):
            r1.merge_with(r2)
        with self.assertRaises(veca.rules.IncompatibleRuleError):
            r2.merge_with(r1)

    def test_merge_with_other_oneof_rule(self):
        r1 = veca.rules.OneOfRule({1, 2})
        r2 = veca.rules.OneOfRule({4, 5})

        self.assertEqual(r1.merge_with(r2), veca.rules.OneOfRule({1, 2, 4, 5}))
        self.assertEqual(r2.merge_with(r1), veca.rules.OneOfRule({1, 2, 4, 5}))

    def test_merge_with_equality_rule(self):
        r1 = veca.rules.OneOfRule({1, 2})
        r2 = veca.rules.EqualityRule(5)

        self.assertEqual(r1.merge_with(r2), veca.rules.OneOfRule({1, 2, 5}))
        self.assertEqual(r2.merge_with(r1), veca.rules.OneOfRule({1, 2, 5}))

    def test_merge_with_ovelapping_values(self):
        r1 = veca.rules.OneOfRule({1, 2, 3})
        r2 = veca.rules.OneOfRule({2, 3, 4})
        r3 = veca.rules.OneOfRule({2, 3})

        self.assertEqual(r1.merge_with(r2), veca.rules.OneOfRule({1, 2, 3, 4}))
        self.assertEqual(r2.merge_with(r1), veca.rules.OneOfRule({1, 2, 3, 4}))

        self.assertEqual(r1.merge_with(r3), veca.rules.OneOfRule({1, 2, 3}))
        self.assertEqual(r3.merge_with(r1), veca.rules.OneOfRule({1, 2, 3}))

    def test_contains_non_oneof_rule(self):
        r1 = veca.rules.OneOfRule({1, 2, 3})
        r2 = veca.rules.EqualityRule(2)
        r3 = veca.rules.IntervalRule(0, 5)

        self.assertTrue(r1.contains(r2))
        self.assertFalse(r1.contains(r3))

    def test_contains(self):
        r1 = veca.rules.OneOfRule({1, 2, 3})
        r2 = veca.rules.OneOfRule({1, 2})

        self.assertTrue(r1.contains(r1))
        self.assertTrue(r1.contains(r2))

        r1 = veca.rules.OneOfRule({1, 2, 3})
        r2 = veca.rules.OneOfRule({2, 3, 4})
        self.assertFalse(r1.contains(r2))

        r1 = veca.rules.OneOfRule({1, 2, 3})
        r2 = veca.rules.OneOfRule({7, 8, 9})
        self.assertFalse(r1.contains(r2))

        r1 = veca.rules.OneOfRule({1, 2, 3})
        r2 = veca.rules.EqualityRule(2)
        r3 = veca.rules.EqualityRule(10)
        self.assertTrue(r1.contains(r2))
        self.assertFalse(r1.contains(r3))


class TestExplanatoryVariable(unittest.TestCase):
    def test_can_merge_with_discretized_variables(self):
        x = np.random.normal(0, 1, size=50)
        df = pd.DataFrame(x, columns=["x"])
        df_discretized = pp.generate_explanatory_features(df)

        variables = df_discretized.columns
        assert len(variables) >= 3, "Too few discretized bins to perform test"
        v1, v2, v3, *_ = variables

        self.assertTrue(v1.can_merge_with(v1))

        self.assertTrue(v1.can_merge_with(v2))
        self.assertTrue(v2.can_merge_with(v1))

        self.assertTrue(v2.can_merge_with(v3))
        self.assertTrue(v3.can_merge_with(v2))

        self.assertFalse(v1.can_merge_with(v3))
        self.assertFalse(v3.can_merge_with(v1))

    def test_merge_with_discretized_variables(self):
        x = np.random.normal(0, 1, size=50)
        df = pd.DataFrame(x, columns=["x"])
        df_discretized = pp.generate_explanatory_features(df)

        variables = df_discretized.columns
        assert len(variables) >= 3, "Too few discretized bins to perform test"
        v1, v2, v3, *_ = variables

        v1v2 = v1.merge_with(v2)
        self.assertIsInstance(v1v2, veca.data.variable.DerivedVariable)
        self.assertEqual(v1v2.rule.lower, v1.rule.lower)
        self.assertEqual(v1v2.rule.upper, v2.rule.upper)

        v2v1 = v2.merge_with(v1)
        self.assertEqual(v1v2, v2v1)

        # Test that we can merge a variable already contained into the interval
        v_combined = v1.merge_with(v2)
        v_combined_2 = v_combined.merge_with(v2)
        self.assertEqual(v_combined, v_combined_2)

        # Test that we can't merge non-neighboring bins
        with self.assertRaises(ValueError):
            v1.merge_with(v3)
        with self.assertRaises(ValueError):
            v3.merge_with(v1)

    def test_can_merge_with_one_hot_encoded_features(self):
        x = ["r", "g", "b"] * 5
        np.random.shuffle(x)

        df = pd.DataFrame(pd.Categorical(x), columns=["x"])
        df_encoded = pp.generate_explanatory_features(df)

        variables = df_encoded.columns
        assert len(variables) == 3, "One hot encoding should produce exactly 3 variables"
        v1, v2, v3 = variables

        self.assertTrue(v1.can_merge_with(v2))
        self.assertTrue(v1.can_merge_with(v3))

        self.assertTrue(v2.can_merge_with(v1))
        self.assertTrue(v2.can_merge_with(v3))

        self.assertTrue(v3.can_merge_with(v1))
        self.assertTrue(v3.can_merge_with(v2))

    def test_merge_with_one_hot_encoded_features(self):
        x = ["r", "g", "b"] * 5
        np.random.shuffle(x)

        df = pd.DataFrame(pd.Categorical(x), columns=["x"])
        df_encoded = pp.generate_explanatory_features(df)

        variables = df_encoded.columns
        assert len(variables) == 3, "One hot encoding should produce exactly 3 variables"
        v1, v2, v3 = variables

        v1v2 = v1.merge_with(v2)
        self.assertIsInstance(v1v2, veca.data.variable.DerivedVariable)
        self.assertEqual(v1v2.rule, veca.rules.OneOfRule({v1.rule.value, v2.rule.value}))

        v2v1 = v2.merge_with(v1)
        self.assertEqual(v1v2, v2v1)

        v1v3 = v1.merge_with(v3)
        self.assertIsInstance(v1v3, veca.data.variable.DerivedVariable)
        self.assertEqual(v1v3.rule, veca.rules.OneOfRule({v1.rule.value, v3.rule.value}))

        v3v1 = v3.merge_with(v1)
        self.assertEqual(v1v3, v3v1)

