import matplotlib.pyplot as plt
import re
import os

import argparse

def main():
   # Load the baseline losses from the text file
   parser = argparse.ArgumentParser()
   parser.add_argument("--dir", type=str, help="Path to the baseline losses directory", required=True)
   parser.add_argument("--model", type=str, choices=["granite", "qwen"], default="qwen", help="Model name for plot title")
   args = parser.parse_args()

   # Sanity check to ensure the directory exists and contains files
   if not os.path.exists(args.dir):
      raise ValueError(f"Directory {args.dir} does not exist. Please provide a valid directory with loss files.")
   elif len(os.listdir(args.dir)) == 0:
      raise ValueError(f"No files found in directory {args.dir}. Please provide a valid directory with loss files.")


   files = os.listdir(args.dir)
   fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), sharex=True)

   for idx, file in enumerate(files):
      with open(os.path.join(args.dir, file), 'r') as f:
         content = f.read()

      # Extract all <td>...</td> values
      td_values = re.findall(r'<td>([\d\.]+)</td>', content)
      # Convert to float or int as appropriate
      td_values = [float(x) if '.' in x else int(x) for x in td_values]

      # Steps, training losses, validation losses
      # Can slice b/c the structure is consistently <td>step</td><td>train_loss</td><td>val_loss</td>
      steps = td_values[0::3]
      train_losses = td_values[1::3]
      val_losses = td_values[2::3]

      label_name = file.split(".")[0]
      ax1.plot(steps, train_losses, linestyle='-', label=f'{label_name} training loss')
      ax2.plot(steps, val_losses, linestyle='--', label=f'{label_name} validation loss')

   ax1.set_xlabel("Steps")
   ax1.set_ylabel("Training Loss")
   ax1.legend()
   ax1.grid(True)
   
   ax2.set_xlabel("Steps")
   ax2.set_ylabel("Validation Loss")
   ax2.legend()
   ax2.grid(True)

   match args.model:
      case "granite":
         fig.suptitle("Granite 4 LoRA Rank vs Loss")
      case "qwen":
         fig.suptitle("Qwen 3.5 LoRA Rank vs Loss")

   plt.tight_layout() # Adjust layout to prevent overlap
   plt.show()

if __name__ == "__main__":
    main()