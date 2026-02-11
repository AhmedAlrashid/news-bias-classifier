# Read annotations_metadata.csv and only include rows where the label is "hate"
# I don't think we can use the context column
# Since this is all test data, we can eliminate the rows where the label is "relation" to simplify things

import polars as pl
import os

def main():

    # Read the CSV file
    print("cwd: ", os.getcwd())
    df = pl.read_csv("cleaned_stormfront/annotations_metadata.csv", columns=["file_id", "label"])

    # Filter for rows where the label is "hate"
    files_to_delete = df.filter(pl.col("label") != "hate")
    df = df.filter(pl.col("label") == "hate")

    # print("Files to delete:")
    # print(files_to_delete)

    # print("Files to keep:")
    # print(df)

    # Read the text files corresponding to the file_ids and create a new DataFrame with the text and labels
    texts = []
    for file_id in df["file_id"]:
        with open(f"cleaned_stormfront/all_files/{file_id}.txt", "r") as f:
            text = f.read()
            texts.append(text)

    # Delete the files that are not labeled as "hate"
    for file_id in files_to_delete["file_id"]:
       try:
          os.remove(f"cleaned_stormfront/all_files/{file_id}.txt")
       except FileNotFoundError:
          continue
       
    print(f"Number of files labeled as 'hate': {len(texts)}")
    print(f"Number of files in all_files: {len(os.listdir('cleaned_stormfront/all_files'))}")

    # Create a new DataFrame with the text and labels
    result_df = pl.DataFrame({"text": texts, "label": "Far Right"})

    # Save the result to a new CSV file
    result_df.write_csv("cleaned_stormfront/hate_data.csv")

if __name__ == "__main__":
    main()