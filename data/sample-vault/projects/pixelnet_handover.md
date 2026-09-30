# PixelNet — From-Scratch Image Classifier

## Status: DONE

### What It Is
A multi-layer neural network built entirely from scratch in NumPy — no PyTorch, no TensorFlow, no autograd library. Classifies CIFAR-10 images. Final test accuracy: 91.3%.

### Architecture
- Input: 32x32x3 images, flattened to 3072
- Hidden layers: 3 fully connected (512 → 256 → 128) with ReLU
- Batch normalization after each hidden layer
- Dropout (0.3) during training
- Output: 10 classes, softmax
- Loss: cross-entropy
- Optimizer: SGD with momentum (0.9) and learning rate decay

### What I Implemented From Scratch
- Forward pass (matrix multiplications, activations)
- Backpropagation (gradient computation through every layer)
- Batch normalization (forward and backward)
- Dropout
- SGD with momentum
- Learning rate scheduling (step decay)
- Mini-batch training loop
- Accuracy evaluation

### Key Numbers
- Test accuracy: 91.3% (after batch norm fix)
- Training time: ~45 minutes on my laptop CPU
- Parameters: ~1.8M
- Previous best before batch norm: 89.7%

### What I Learned
- Backprop is just chain rule applied carefully — the math isn't hard, the indexing is
- Batch norm was the single biggest accuracy jump (~1.5%)
- Learning rate decay matters more than I expected
- NumPy broadcasting is powerful but the shape errors are brutal to debug

### Repository
github.com/arjunmehta/pixelnet

### Timeline
- Started: June 2026 (as a "let me try ML" experiment)
- Working classifier: July 2026
- Batch norm + optimizations: August 2026
- Final version: September 2026
