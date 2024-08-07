
"""Tests for the Antlr Tokenizer."""

import unittest

from bot.tokenizer.antlr_tokenizer import AntlrTokenizer
from bot.tokenizer.grammars.JavaScriptLexer import \
    JavaScriptLexer


class AntlrTokenizerTest(unittest.TestCase):
  """Tests for AntlrTokenizer"""

  def test_empty_list_on_empty_data(self):
    """Test Tokenizer works on empty list"""
    tokenizer = AntlrTokenizer(JavaScriptLexer)
    data = b''

    tokens = tokenizer.tokenize(data)

    self.assertEqual(tokens, [])

  def test_tokenize_simple_js_file(self):
    """Test tokenizer works with sample JS"""
    tokenizer = AntlrTokenizer(JavaScriptLexer)
    txt = b"""async function process(array) {
          for await (let i of array) {
              doSomething(i);
            }
          }"""

    tokens = tokenizer.tokenize(txt)
    self.assertEqual(tokens, [
        'async', ' ', 'function', ' ', 'process', '(', 'array', ')', ' ', '{',
        '\n', '          ', 'for', ' ', 'await', ' ', '(', 'let', ' ', 'i', ' ',
        'of', ' ', 'array', ')', ' ', '{', '\n', '              ',
        'doSomething', '(', 'i', ')', ';', '\n', '            ', '}', '\n',
        '          ', '}'
    ])

  def test_combine_same_as_orig(self):
    """Tests the token combiner"""
    tokenizer = AntlrTokenizer(JavaScriptLexer)
    txt = b"""async function process(array) {
          for await (let i of array) {
              doSomething(i);
            }
          }"""

    tokens = tokenizer.tokenize(txt)

    self.assertEqual(tokenizer.combine(tokens), txt)

  def test_tokenizes_malformed_without_error(self):
    """Tests tokenizer doesnt error on garbage input"""
    tokenizer = AntlrTokenizer(JavaScriptLexer)
    txt = b'aasdfj1  1jhsdf9 1 3@ 1 + => adj 193'

    tokens = tokenizer.tokenize(txt)
    self.assertEqual(tokens, [
        'aasdfj1', '  ', '1', 'jhsdf9', ' ', '1', ' ', '3', '@', ' ', '1', ' ',
        '+', ' ', '=>', ' ', 'adj', ' ', '193'
    ])
