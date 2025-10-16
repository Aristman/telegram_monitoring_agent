"""
Анализаторы сообщений
"""

from .summary_analyzer import SummaryAnalyzer
from .informational_analyzer import InformationalAnalyzer
from .discussion_analyzer import DiscussionAnalyzer
from .howto_analyzer import HowToAnalyzer

__all__ = [
    'SummaryAnalyzer',
    'InformationalAnalyzer',
    'DiscussionAnalyzer',
    'HowToAnalyzer',
]
