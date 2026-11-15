"""Runtime modules owned by individual skill bundles and shared contracts.

This package stays import-light on purpose: the standalone spec validator
imports :mod:`easy_cheese.shared.document_rules` without cattrs installed, so
no eager import here may reach the schema runtime.
"""
