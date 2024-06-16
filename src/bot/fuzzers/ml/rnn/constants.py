
"""Constants for ML RNN model."""

# Model name.
RNN_MODEL_NAME = 'rnn'

# Num of chars to be trained in one batch.
TRAINING_SEQLEN = 30

# Num of chars to be validated in one batch.
VALIDATION_SEQLEN = 1024

# Size of the alphabet that we work with.
ALPHA_SIZE = 256

# Num of sequences in a batch.
BATCH_SIZE = 100

# Number of epochs.
EPOCHS = 10

# Size of internal states in a neural cell.
HIDDEN_STATE_SIZE = 512

# Number of hidden layers.
HIDDEN_LAYER_SIZE = 3

# Learning rate.
LEARNING_RATE = 0.001

# Dropout probability (keep rate).
DROPOUT_PKEEP = 0.8

# Max num of models to keep during training.
MAX_TO_KEEP = 10

# Display training progress for every 50 batches.
DISPLAY_FREQ = 50

# Length of progress bar.
DISPLAY_LEN = 138

# Training script name.
TRAINING_SCRIPT_NAME = 'train.py'

# Generation script name.
GENERATION_SCRIPT_NAME = 'generate.py'

# Model files suffix.
MODEL_DATA_SUFFIX = '.data-00000-of-00001'
MODEL_INDEX_SUFFIX = '.index'

# Model parameter arguments.
BATCH_SIZE_ARGUMENT_PREFIX = '--batch-size='
HIDDEN_STATE_ARGUMENT_PREFIX = '--hidden-state-size='
HIDDEN_LAYER_ARGUMENT_PREFIX = '--hidden-layer-size='

# Training script arguments.
INPUT_DIR_ARGUMENT_PREFIX = '--input-dir='
MODEL_DIR_ARGUMENT_PREFIX = '--model-dir='
LOG_DIR_ARGUMENT_PREFIX = '--log-dir='

# Generation script arguments.
OUTPUT_DIR_ARGUMENT_PREFIX = '--output-dir='
MODEL_PATH_ARGUMENT_PREFIX = '--model-path='
GENERATION_COUNT_ARGUMENT_PREFIX = '--count='


class ExitCode(object):
  """Exit code for training and generation."""
  SUCCESS = 0
  INVALID_PATH = 1
  CORPUS_TOO_SMALL = 2
  TENSORFLOW_ERROR = 3
