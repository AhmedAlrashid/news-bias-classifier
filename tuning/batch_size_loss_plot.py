import numpy as np
import matplotlib.pyplot as plt
import re
import os

import argparse

def main():
   # Load the baseline losses from the text file
   parser = argparse.ArgumentParser()
   parser.add_argument("--dir", type=str, help="Path to the baseline losses directory", required=True)
   parser.add_argument("--model", type=str, choices=["granite", "qwen"], default="granite", help="Model name for plot title")
   args = parser.parse_args()

   # Sanity check to ensure the directory exists and contains files
   if not os.path.exists(args.dir):
      raise ValueError(f"Directory {args.dir} does not exist. Please provide a valid directory with loss files.")
   elif len(os.listdir(args.dir)) == 0:
      raise ValueError(f"No files found in directory {args.dir}. Please provide a valid directory with loss files.")

   losses = [[float(x) for x in re.findall(r'<td>(\d+\.\d+)</td>', open(os.path.join(args.dir, file)).read())] for file in os.listdir(args.dir)]

   # Total steps max
   total_steps = max(len(loss) for loss in losses)
   print(f"Max number of steps: {total_steps}")

   # Create normalized epoch values (0 → 1)

   epochs = np.linspace(0, 1, total_steps)

   window = 20

   # Plot using smooth losses (moving average of 20)
   plt.figure(figsize=(10, 5))

   for i in range(len(losses)):
      smoothed = np.convolve(losses[i], np.ones(window)/window, mode='valid')
      smoothed_epochs = epochs[:len(smoothed)]
      label_name = os.listdir(args.dir)[i].split(".")[0]
      plt.plot(smoothed_epochs, smoothed, linewidth=2, label=label_name)

   plt.legend()

   plt.xlabel("Epoch")
   plt.ylabel("Training Loss")
   match args.model:
      case "granite":
         plt.title("Granite 4 Training Loss")
      case "qwen":
         plt.title("Qwen 3.5 Training Loss")
         
   plt.grid(True)
   plt.tight_layout()
   plt.show()

if __name__ == "__main__":
    main()