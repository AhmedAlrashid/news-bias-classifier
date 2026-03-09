import os
import glob

from datasets import load_dataset

# Print distribution of bias labels
def print_bias_distribution(split, split_name):
    bias_labels = split["bias"]
    total = len(bias_labels)
    from collections import Counter
    counts = Counter(bias_labels)
    print(f"Distribution of bias column in {split_name} set:")
    for value, count in counts.items():
        percent = 100 * count / total
        print(f"Label: {value}, Count: {count}, Percent: {percent:.2f}%")
    print("\n")

def main():
    # Remove all json files from output directory
    print(os.getcwd())
    output_dir = "output"
    output_path = os.path.join(os.getcwd(), output_dir)
    print(f"Output path: {output_path}")
    if os.path.exists(output_path):
        json_files = glob.glob(os.path.join(output_path, "*.json"))
        for json_file in json_files:
            os.remove(json_file)
        print(f"Removed {len(json_files)} json files from {output_dir} directory.")
    else:
        print(f"{output_dir} directory does not exist.")

    # Create a Hugging Face dataset from the the csv files
    csv_files = glob.glob(os.path.join(output_path, "*.csv"))
    if not csv_files:
        print("No csv files found in output directory.")
        return
    
    dataset = load_dataset("csv", data_files=csv_files)
    print(f"Loaded dataset with {len(dataset)} records.")

    # Remove entries where summary is null or empty
    dataset = dataset.filter(lambda x: x["summary"] is not None and x["summary"] != "")
    print(f"Dataset after removing entries with null or empty summaries: {len(dataset)} records.")

    # Split the dataset into train, validation and test sets

    # 70% train, 15% validation, 15% test is standard ratio for splitting datasets.
    print("Splitting dataset into train, validation and test sets...")
    dataset = dataset["train"].train_test_split(test_size=0.3, seed=42) # Split into train and test sets
    dataset["validation"] = dataset["test"].train_test_split(test_size=0.5, seed=42)["train"] # Split test set into validation and test sets
    dataset["test"] = dataset["test"].train_test_split(test_size=0.5, seed=42)["test"] # Split test set into validation and test sets
    print(dataset)

    # Print distribution of the bias column in the train, validation and test sets
    print_bias_distribution(dataset["train"], "train")
    print_bias_distribution(dataset["validation"], "validation")
    print_bias_distribution(dataset["test"], "test")

    # Get length of each split
    print(f"Length of train set: {len(dataset['train'])}")
    print(f"Length of validation set: {len(dataset['validation'])}")
    print(f"Length of test set: {len(dataset['test'])}")

    print("Total length of dataset: ", len(dataset["train"]) + len(dataset["validation"]) + len(dataset["test"]))

    #Output the dataset to csv files
    # print("Saving dataset to csv files...")
    # dataset["train"].to_csv(os.path.join(output_path, "train.csv"), index=False)
    # dataset["validation"].to_csv(os.path.join(output_path, "validation.csv"), index=False)
    # dataset["test"].to_csv(os.path.join(output_path, "test.csv"), index=False)
    
    
    print("Saving dataset to Hugging Face")
    # dataset.push_to_hub("avanishd/ground-news-2026")


if __name__ == "__main__":
    main()