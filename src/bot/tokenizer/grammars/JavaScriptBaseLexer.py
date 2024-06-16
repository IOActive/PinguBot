
"""Translation from Java code for JavaScriptBaseLexer made to work with
JavaScriptLexer"""

import antlr4


class JavaScriptBaseLexer(antlr4.Lexer):

  def __init__(self, input, output):
    super(JavaScriptBaseLexer, self).__init__(input, output)
    self._scopeStrictModes = []
    self._lastToken = None
    self._useStrictDefault = False
    self._useStrictCurrent = False

  def IsStartOfFile(self):
    return self._lastToken == None

  def getStrictDefault(self):
    return self._useStrictDefault

  def setUseStrictDefault(self, bool):
    self._useStrictDefault = bool
    self._useStrictCurrent = bool

  def IsStrictMode(self):
    return self._useStrictCurrent

  def nextToken(self):
    next = super(JavaScriptBaseLexer, self).nextToken()
    if (next.channel == antlr4.Token.DEFAULT_CHANNEL):
      self._lastToken = next

    return next

  def ProcessOpenBrace(self):
    if len(self._scopeStrictModes) > 0 and self._scopeStrictModes[-1]:
      self._useStrictCurrent = True
    else:
      self._useStrictCurrent = self._useStrictDefault

    self._scopeStrictModes.append(self._useStrictCurrent)

  def ProcessCloseBrace(self):
    if len(self._scopeStrictModes) > 0:
      self._useStrictCurrent = self._scopeStrictModes.pop()
    else:
      self._useStrictCurrent = self._useStrictDefault

  def ProcessStringLiteral(self):
    if self._lastToken == None or self._lastToken.type == self.OpenBrace:
      text = super(JavaScriptBaseLexer, self).text
      if text == '"use strict"' or text == '\'use strict\'':
        if len(self._scopeStrictModes) > 0:
          self._scopeStrictModes.pop()
        self._useStrictCurrent = True
        self._scopeStrictModes.append(self._useStrictCurrent)

  def IsRegExPossible(self):
    if self._lastToken == None:
      return True

    if self._lastToken in [
        self.Identifier, self.NullLiteral, self.BooleanLiteral, self.This,
        self.CloseBracket, self.CloseParen, self.OctalIntegerLiteral,
        self.StringLiteral, self.PlusPlus, self.MinusMinus
    ]:
      return False
    return True
