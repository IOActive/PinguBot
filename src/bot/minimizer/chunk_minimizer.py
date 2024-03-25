
"""Fast minimizer that attempts to remove tokens grouped in chunks."""

import functools

from . import errors
from . import minimizer
from . import utils


class ChunkMinimizer(minimizer.Minimizer):
  """Minimizer to replicate the old ClusterFuzz minimization strategy."""

  def __init__(self, *args, **kwargs):
    self.chunk_sizes = self._handle_constructor_argument(
        'chunk_sizes', kwargs, default=[10, 4, 1])
    minimizer.Minimizer.__init__(self, *args, **kwargs)

  def _execute(self, data):
    """Minimize |data| using the algorithm from CF (but backwards)."""
    testcase = minimizer.Testcase(data, self)
    if not self.validate_tokenizer(data, testcase):
      raise errors.TokenizationFailureError('Chunk Minimizer')

    for lines_to_remove in self.chunk_sizes:
      remaining_tokens = testcase.get_required_token_indices()
      for end_index in range(len(remaining_tokens), 0, -lines_to_remove):
        start_index = max(0, end_index - lines_to_remove)
        hypothesis = remaining_tokens[start_index:end_index]
        testcase.prepare_test(hypothesis)

      testcase.process()

    return testcase

  @staticmethod
  def run(data, thread_count=minimizer.DEFAULT_THREAD_COUNT, file_extension=''):
    """Minimize |data| using the old strategy from CF."""
    minimizer_round_1 = ChunkMinimizer(
        utils.test,
        max_threads=thread_count,
        tokenizer=utils.tokenize,
        token_combiner=utils.token_combiner,
        chunk_sizes=[80, 40, 20],
        file_extension=file_extension)

    full_tokenizer = functools.partial(utils.tokenize, level=1)
    minimizer_round_2 = ChunkMinimizer(
        utils.test,
        max_threads=thread_count,
        tokenizer=full_tokenizer,
        token_combiner=utils.token_combiner,
        chunk_sizes=[10, 4, 1],
        file_extension=file_extension)

    result = minimizer_round_1.minimize(data)
    result = minimizer_round_2.minimize(result)
    return result
