# NewsMin

Classifying political lean in U.S. news articles.

[**Dataset and models**](https://huggingface.co/collections/avanishd/politicial-lean-detection).

See pyproject.toml for a list of libraries used (the dependency information won't be accurate since the Granite and Qwen finetunes need different versions of transformers and Unsloth).

## Setup

```
uv sync
uvx playwright install
```

## Project Structure

```
├── src/
│   ├── data/                # Manual and synthetic data creation scripts
│   │   ├── input/           # CSV files created by scraper and synthetic generation
│   │   ├── rephrase.ipynb   # SmolLM2-1B synthetic generation notebook
│   │   └── scraper.py       # Ground News scraper code
│   ├── eval/                # LLM inference and evaluation scripts
│   ├── models/              # Fine-tuning notebooks
│   ├── results/             # LLM outputs on test set and evaluation metrics
│   ├── scraper/             # Manual and synthetic data and dataset creation scripts
│   └── tuning/              # LLM tuning results and plotting (matplotlib) scripts
```