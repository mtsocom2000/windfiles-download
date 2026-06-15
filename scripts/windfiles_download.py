#!/usr/bin/env python3
"""Windfiles Cloud Drive 下载脚本 - 入口点"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.cli import main
main()
