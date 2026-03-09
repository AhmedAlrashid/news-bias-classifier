import numpy as np
import matplotlib.pyplot as plt
import re

def main():
    # Load the baseline losses from the text file
    baseline_losses = [] # Batch size = 2, gradient accumulation = 4
    batch_size_16_losses = [] # Batch size = 4, gradient accumulation = 4
    batch_size_32_grad_8_losses = [] # Batch size = 4, gradient accumulation = 8
    batch_size_32_grad_4_losses = [] # Batch size = 8, gradient accumulation = 4
    
    # Parse the HTML table to extract the loss values
    with open("tuning/baseline_losses.txt", "r") as f:
       html = f.read()
       baseline_losses = [float(x) for x in re.findall(r'<td>(\d+\.\d+)</td>', html)]

    with open("tuning/batch_size_16_losses.txt", "r") as f:
       html = f.read()
       batch_size_16_losses = [float(x) for x in re.findall(r'<td>(\d+\.\d+)</td>', html)]

    with open("tuning/batch_size_32_grad_8_losses.txt", "r") as f:
       html = f.read()
       batch_size_32_grad_8_losses = [float(x) for x in re.findall(r'<td>(\d+\.\d+)</td>', html)]
    
    with open("tuning/batch_size_32_grad_4_losses.txt", "r") as f:
       html = f.read()
       batch_size_32_grad_4_losses = [float(x) for x in re.findall(r'<td>(\d+\.\d+)</td>', html)]

    # Total steps
    # Since baseline is the most number of steps, no need to find the max
    total_steps = len(baseline_losses)
    print(f"Max number of steps: {total_steps}")

    # Create normalized epoch values (0 → 1)
    
    epochs = np.linspace(0, 1, total_steps)

    window = 20
    smoothed = np.convolve(baseline_losses, np.ones(window)/window, mode='valid')
    smoothed_epochs = epochs[:len(smoothed)]

    batch_size_16_smoothed = np.convolve(batch_size_16_losses, np.ones(window)/window, mode='valid')
    batch_size_16_smoothed_epochs = epochs[:len(batch_size_16_smoothed)]

    batch_size_32_grad_8_smoothed = np.convolve(batch_size_32_grad_8_losses, np.ones(window)/window, mode='valid')
    batch_size_32_grad_8_smoothed_epochs = epochs[:len(batch_size_32_grad_8_smoothed)]

    batch_size_32_grad_4_smoothed = np.convolve(batch_size_32_grad_4_losses, np.ones(window)/window, mode='valid')
    batch_size_32_grad_4_smoothed_epochs = epochs[:len(batch_size_32_grad_4_smoothed)]

    # Plot
    plt.figure(figsize=(10, 5))
    # plt.plot(epochs, losses, linewidth=1)
    
    # plt.plot(epochs, baseline_losses, alpha=0.3, label="Raw Loss Baseline")
    plt.plot(smoothed_epochs, smoothed, linewidth=2, label="Smoothed Loss Baseline")
    plt.plot(batch_size_16_smoothed_epochs, batch_size_16_smoothed, linewidth=2, label="Batch Size 16 Smoothed Loss")
    plt.plot(batch_size_32_grad_8_smoothed_epochs, batch_size_32_grad_8_smoothed, linewidth=2, label="Batch Size 32, Grad 8 Smoothed Loss")
    plt.plot(batch_size_32_grad_4_smoothed_epochs, batch_size_32_grad_4_smoothed, linewidth=2, label="Batch Size 32, Grad 4 Smoothed Loss")
    plt.legend()
    
    plt.xlabel("Epoch")
    plt.ylabel("Training Loss")
    plt.title("Granite 4 Training Loss")
    plt.grid(True)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()