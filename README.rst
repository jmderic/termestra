.. -*- coding: utf-8; fill-column: 88; -*-

.. organize section decoration according to the Python's Style Guide
   for documenting as given here:
   https://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html#sections

   # with overline, for parts
   * with overline, for chapters
   =, for sections
   -, for subsections
   ^, for subsubsections
   ", for paragraphs

   We start assuming our "top level" is a chapter

*******************************
Termestra Terminal Orchestrator
*******************************

Intro TBD

.. contents:: Table of Contents
   :local:

..   :backlinks: none

Overview
========

TBD

Running Termestra
=================

Run the Termestra "base" command from this directory for testing as follows::

.. code-block:: none

  $ ./termestra/termestra.py base --tab-names="Tab 1, Tab 2" --log-level=DEBUG

This will create a tmux enabled gnome terminal with two tabs, Tab 1 and Tab 2.  If you
want to test line bufffering, go to either tab and type the following:

.. code-block:: none

  $ ./termestra/line_test.py 137 4080 10000

That will generate 3 lines of length 137, 4080, and 10000 consisting of the repeating
string "0123456789".  Between lines, the digit sequence is maintained to allow detection
of "off by one" issues.

The activity of the ``termestra.py base`` daemon is logged to a file styled as follows::

.. code-block:: none

  /tmp/termestra-base-20240523_052356.log

with the timestamp changing on each run.  Note that the pipes that allow the daemon to
read the activity in the terminal are styled as follows::

.. code-block:: none

  /tmp/termestra-base-20240523_052356-pipe-1

There is one pipe for each tab in the ``--tab-names`` cli argument.  And the pipes are
not unlinked when the daemon exits; they just cease to be read.

To shut down the daemon, type the following in either tab::

.. code-block:: none

  $ kill $(cat /tmp/termestra-base.pid | head -n 1)

That will cause the daemon to exit, but it will not shut down the constructed terminal.
Inspection of the log file shows this activity.
