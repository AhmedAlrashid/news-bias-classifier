import argparse
import polars as pl
from sklearn.metrics import mean_absolute_error, classification_report, confusion_matrix, ConfusionMatrixDisplay

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", help="Path to the csv file", required=True)
    args = parser.parse_args()

    # Load the CSV file using Polars
    df = pl.read_csv(args.csv)

    # Extract the text after the word assistant in predicted_bias and convert it to a float
    # This only works for the granite models since they output the bias in the format "assistantX.X" where X.X is the bias value

    args_csv_str = str(args.csv)
    if "granite" in args_csv_str:
        # Granite output is in format "assistantX.X" where X.X is the bias value
        df = df.with_columns(
            pl.col("predicted_bias")
            .str.extract(r"assistant([+-]?\d+\.?\d*)", 1)
            .cast(pl.Float64)
            .alias("predicted_bias_value")
        )
    else:
        # Qwen output is in format "assistant <think> </think> X.X" (spaces are newlines in actual output, see csv)
        df = df.with_columns(
            pl.col("predicted_bias")
            .str.extract(r"assistant\s*<think>\s*</think>\s*([+-]?\d+\.?\d*)", 1)
            .cast(pl.Float64)
            .alias("predicted_bias_value")
        )

    # print(df.head())

    # Map the predicted bias values to labels
    """
    -3.0 <= bias < -2.0: "Far Left"
    -2.0 <= bias < -1.0: "Left"
    -1.0 <= bias < 0.0: "Lean Left"
    0.0 <= bias < 1.0: "Center"
    1.0 <= bias < 2.0: "Lean Right"
    2.0 <= bias < 3.0: "Right"
    bias >= 3.0: "Far Right"
    """
    
    df = df.with_columns(
        pl.when(pl.col("predicted_bias_value").is_between(float('-inf'), -2.0, closed="left")).then(pl.lit("Far Left"))
        .when(pl.col("predicted_bias_value").is_between(-2.0, -1.0, closed="left")).then(pl.lit("Left"))
        .when(pl.col("predicted_bias_value").is_between(-1.0, 0.0, closed="left")).then(pl.lit("Lean Left"))
        .when(pl.col("predicted_bias_value").is_between(0.0, 1.0, closed="left")).then(pl.lit("Center"))
        .when(pl.col("predicted_bias_value").is_between(1.0, 2.0, closed="left")).then(pl.lit("Lean Right"))
        .when(pl.col("predicted_bias_value").is_between(2.0, 3.0, closed="left")).then(pl.lit("Right"))
        .when(pl.col("predicted_bias_value") >= 3.0).then(pl.lit("Far Right"))
        .otherwise(pl.lit("unknown"))
        .alias("predicted_bias_label")
    )

    # Convert bias column to numeric values for evaluation
    bias_mapping = {
        "Far Left": -3.0,
        "Left": -2.0,
        "Lean Left": -1.0,
        "Center": 0.0,
        "Lean Right": 1.0,
        "Right": 2.0,
        "Far Right": 3.0
    }

    df = df.with_columns(
        pl.col("bias").replace(bias_mapping).alias("bias_value")
    )

    # Print the distribution of predicted bias labels
    print(df["predicted_bias_label"].value_counts())

    # Calculate evaluation metrics (accuracy, MAE, macro F1 score) and save to a text file

    eval_file_name = args.csv.split("/")[-1].replace(".csv", "_eval.txt")
    with open(f"results/{eval_file_name}", "w") as f:
         # Need labels for MAE b/c it only works on numeric values
         f.write("Mean Absolute Error: " + str(mean_absolute_error(df["bias_value"], df["predicted_bias_value"])) + "\n")

         # Zero division b/c model predicts far left and lean right, which we don't have
         f.write("Classification Report:\n" + classification_report(df["bias"], df["predicted_bias_label"], zero_division=0))

    # Generate and save confusion matrix (won't work since y_true doesn't have all the labels that y_pred has)
    # cm = confusion_matrix(df["bias"], df["predicted_bias_label"], labels=list(bias_mapping.values()))
    # disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=list(bias_mapping.keys()))
    # disp.plot(cmap="Blues")
    # disp.figure_.savefig("results/confusion_matrix.png")

if __name__ == "__main__":
    main()