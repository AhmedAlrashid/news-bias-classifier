from datasets import load_dataset
from datasets import concatenate_datasets
def clean_fignews_2024():
    # Load the FIGNEWS-2024 dataset
    ds = load_dataset("CAMeL-Lab/FIGNEWS-2024")
    english_only = ds.filter(lambda row: row["source_language"] == "English")
    removing_irrelevant_columns = english_only.remove_columns(["arabic_mt"])
    removing_irrelevant_columns.save_to_disk("cleaned_fignews_2024")
    return removing_irrelevant_columns
# If you want to take a look at what you just saved:

remoing_irrelevant_columns = clean_fignews_2024("data cleaning/cleaned_fignews_2024")

def look_atsaved_data(clean_data):
    
    merged = concatenate_datasets(
        list(clean_data.values())
    )

    merged.to_csv("fignews_english_2024_all.csv", index=False)
