
"""Gestures handler."""
from bot.platforms import android, linux, windows
from bot.system import environment


def get_gestures(gesture_count):
  """Return a list of random gestures."""
  plt = environment.platform()

  if environment.is_android(plt):
    return android.gestures.get_random_gestures(gesture_count)
  if plt == 'LINUX':
    return linux.gestures.get_random_gestures(gesture_count)
  if plt == 'WINDOWS':
    return windows.gestures.get_random_gestures(gesture_count)

  return []
