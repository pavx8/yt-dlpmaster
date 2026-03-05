from __future__ import annotations

import subprocess
import sys
from importlib import metadata

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.core.ca import get_ca_bundle_info
from app.core.ffmpeg import resolve_ffmpeg_path

APP_NAME = "yt-dlpMaster"
APP_VERSION = "0.1.0"
LGPL_V3_TEXT = """                   GNU LESSER GENERAL PUBLIC LICENSE
                       Version 3, 29 June 2007

 Copyright (C) 2007 Free Software Foundation, Inc. <https://fsf.org/>
 Everyone is permitted to copy and distribute verbatim copies
 of this license document, but changing it is not allowed.


  This version of the GNU Lesser General Public License incorporates
the terms and conditions of version 3 of the GNU General Public
License, supplemented by the additional permissions listed below.

  0. Additional Definitions.

  As used herein, "this License" refers to version 3 of the GNU Lesser
General Public License, and the "GNU GPL" refers to version 3 of the GNU
General Public License.

  "The Library" refers to a covered work governed by this License,
other than an Application or a Combined Work as defined below.

  An "Application" is any work that makes use of an interface provided
by the Library, but which is not otherwise based on the Library.
Defining a subclass of a class defined by the Library is deemed a mode
of using an interface provided by the Library.

  A "Combined Work" is a work produced by combining or linking an
Application with the Library.  The particular version of the Library
with which the Combined Work was made is also called the "Linked
Version".

  The "Minimal Corresponding Source" for a Combined Work means the
Corresponding Source for the Combined Work, excluding any source code
for portions of the Combined Work that, considered in isolation, are
based on the Application, and not on the Linked Version.

  The "Corresponding Application Code" for a Combined Work means the
object code and/or source code for the Application, including any data
and utility programs needed for reproducing the Combined Work from the
Application, but excluding the System Libraries of the Combined Work.

  1. Exception to Section 3 of the GNU GPL.

  You may convey a covered work under sections 3 and 4 of this License
without being bound by section 3 of the GNU GPL.

  2. Conveying Modified Versions.

  If you modify a copy of the Library, and, in your modifications, a
facility refers to a function or data to be supplied by an Application
that uses the facility (other than as an argument passed when the
facility is invoked), then you may convey a copy of the modified
version:

   a) under this License, provided that you make a good faith effort to
   ensure that, in the event an Application does not supply the
   function or data, the facility still operates, and performs
   whatever part of its purpose remains meaningful, or

   b) under the GNU GPL, with none of the additional permissions of
   this License applicable to that copy.

  3. Object Code Incorporating Material from Library Header Files.

  The object code form of an Application may incorporate material from
a header file that is part of the Library.  You may convey such object
code under terms of your choice, provided that, if the incorporated
material is not limited to numerical parameters, data structure
layouts and accessors, or small macros, inline functions and templates
(ten or fewer lines in length), you do both of the following:

   a) Give prominent notice with each copy of the object code that the
   Library is used in it and that the Library and its use are
   covered by this License.

   b) Accompany the object code with a copy of the GNU GPL and this license
   document.

  4. Combined Works.

  You may convey a Combined Work under terms of your choice that,
taken together, effectively do not restrict modification of the
portions of the Library contained in the Combined Work and reverse
engineering for debugging such modifications, if you also do each of
the following:

   a) Give prominent notice with each copy of the Combined Work that
   the Library is used in it and that the Library and its use are
   covered by this License.

   b) Accompany the Combined Work with a copy of the GNU GPL and this license
   document.

   c) For a Combined Work that displays copyright notices during
   execution, include the copyright notice for the Library among
   these notices, as well as a reference directing the user to the
   copies of the GNU GPL and this license document.

   d) Do one of the following:

       0) Convey the Minimal Corresponding Source under the terms of this
       License, and the Corresponding Application Code in a form
       suitable for, and under terms that permit, the user to
       recombine or relink the Application with a modified version of
       the Linked Version to produce a modified Combined Work, in the
       manner specified by section 6 of the GNU GPL for conveying
       Corresponding Source.

       1) Use a suitable shared library mechanism for linking with the
       Library.  A suitable mechanism is one that (a) uses at run time
       a copy of the Library already present on the user's computer
       system, and (b) will operate properly with a modified version
       of the Library that is interface-compatible with the Linked
       Version.

   e) Provide Installation Information, but only if you would otherwise
   be required to provide such information under section 6 of the
   GNU GPL, and only to the extent that such information is
   necessary to install and execute a modified version of the
   Combined Work produced by recombining or relinking the
   Application with a modified version of the Linked Version. (If
   you use option 4d0, the Installation Information must accompany
   the Minimal Corresponding Source and Corresponding Application
   Code. If you use option 4d1, you must provide the Installation
   Information in the manner specified by section 6 of the GNU GPL
   for conveying Corresponding Source.)

  5. Combined Libraries.

  You may place library facilities that are a work based on the
Library side by side in a single library together with other library
facilities that are not Applications and are not covered by this
License, and convey such a combined library under terms of your
choice, if you do both of the following:

   a) Accompany the combined library with a copy of the same work based
   on the Library, uncombined with any other library facilities,
   conveyed under the terms of this License.

   b) Give prominent notice with the combined library that part of it
   is a work based on the Library, and explaining where to find the
   accompanying uncombined form of the same work.

  6. Revised Versions of the GNU Lesser General Public License.

  The Free Software Foundation may publish revised and/or new versions
of the GNU Lesser General Public License from time to time. Such new
versions will be similar in spirit to the present version, but may
differ in detail to address new problems or concerns.

  Each version is given a distinguishing version number. If the
Library as you received it specifies that a certain numbered version
of the GNU Lesser General Public License "or any later version"
applies to it, you have the option of following the terms and
conditions either of that published version or of any later version
published by the Free Software Foundation. If the Library as you
received it does not specify a version number of the GNU Lesser
General Public License, you may choose any version of the GNU Lesser
General Public License ever published by the Free Software Foundation.

  If the Library as you received it specifies that a proxy can decide
whether future versions of the GNU Lesser General Public License shall
apply, that proxy's public statement of acceptance of any version is
permanent authorization for you to choose that version for the
Library.
"""


class AboutDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("About"))
        self.setMinimumWidth(520)

        root = QVBoxLayout(self)

        header = QHBoxLayout()
        icon_label = QLabel()
        icon_label.setFixedSize(40, 40)
        icon = self.windowIcon()
        pixmap = icon.pixmap(40, 40) if not icon.isNull() else QPixmap()
        if not pixmap.isNull():
            icon_label.setPixmap(pixmap)
        else:
            icon_label.setText("Y")
            icon_label.setAlignment(Qt.AlignCenter)

        title_layout = QVBoxLayout()
        title = QLabel(APP_NAME)
        title_font = QFont(title.font())
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        version = QLabel(self.tr("Version {version}").format(version=APP_VERSION))
        title_layout.addWidget(title)
        title_layout.addWidget(version)

        header.addWidget(icon_label)
        header.addLayout(title_layout)
        header.addStretch(1)
        root.addLayout(header)

        tabs = QTabWidget()
        tabs.setObjectName("aboutTabs")
        tabs.setDocumentMode(False)
        tabs.setTabShape(QTabWidget.TabShape.Rounded)
        tabs.setUsesScrollButtons(False)
        tabs.tabBar().setExpanding(True)
        tabs.addTab(self._build_about_tab(), self.tr("About"))
        tabs.addTab(self._build_components_tab(), self.tr("Components"))
        tabs.addTab(self._build_authors_tab(), self.tr("Authors"))
        tabs.addTab(self._build_translation_tab(), self.tr("Translation"))
        tabs.addTab(self._build_license_tab(), self.tr("License"))
        root.addWidget(tabs)

        close_btn = QPushButton(self.tr("Close"))
        close_btn.clicked.connect(self.accept)
        root.addWidget(close_btn, 0, Qt.AlignRight)
        self.setFixedHeight(self.sizeHint().height())

    def _build_components_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        ca_info = get_ca_bundle_info()
        lines = [
            self.tr("Python: {version}").format(version=sys.version.split()[0]),
            self.tr("PySide6: {version}").format(version=self._package_version("PySide6")),
            self.tr("yt-dlp: {version}").format(version=self._package_version("yt-dlp")),
            self.tr("yt-dlp-ejs: {version}").format(version=self._package_version("yt-dlp-ejs")),
            self.tr("certifi: {version}").format(version=ca_info.certifi_version),
            self.tr("SSL_CERT_FILE: {value}").format(value=ca_info.ssl_cert_file or self.tr("system default")),
            self.tr("ffmpeg: {version}").format(version=self._ffmpeg_version()),
        ]
        layout.addWidget(QLabel("\n".join(lines)))
        layout.addStretch(1)
        return widget

    def _build_about_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        label = QLabel(
            self.tr(
                "Convenient and multifunctional GUI for downloading video and audio "
                "from various resources, built with Python and the PySide, yt-dlp, "
                "yt-dlp-ejs, and FFmpeg libraries"
            )
        )
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addStretch(1)
        return widget

    def _build_authors_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        label = QLabel(
            self.tr(
                "PavX (Platonov A.V.) - author, coder "
                "(<a href=\"mailto:admin@pavx.org\">admin@pavx.org</a>)"
            )
        )
        label.setTextFormat(Qt.RichText)
        label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        label.setOpenExternalLinks(True)
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addStretch(1)
        return widget

    def _build_license_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        text = QPlainTextEdit()
        text.setReadOnly(True)
        text.setPlainText(LGPL_V3_TEXT)
        layout.addWidget(text)
        layout.addStretch(1)
        return widget

    def _build_translation_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        label = QLabel(
            self.tr(
                "Russian: Platonov A.V. "
                "(<a href=\"mailto:admin@pavx.org\">admin@pavx.org</a>)<br/>"
                "English (US): Platonov A.V. "
                "(<a href=\"mailto:admin@pavx.org\">admin@pavx.org</a>)"
            )
        )
        label.setTextFormat(Qt.RichText)
        label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        label.setOpenExternalLinks(True)
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addStretch(1)
        return widget

    @staticmethod
    def _package_version(package_name: str) -> str:
        try:
            return metadata.version(package_name)
        except metadata.PackageNotFoundError:
            return "not installed"

    @staticmethod
    def _ffmpeg_version() -> str:
        ffmpeg_path = resolve_ffmpeg_path()
        if not ffmpeg_path:
            return "not found"

        try:
            proc = subprocess.run(
                [ffmpeg_path, "-version"],
                capture_output=True,
                text=True,
                check=False,
                timeout=3,
            )
        except Exception:  # noqa: BLE001
            return "unknown"

        first_line = (proc.stdout or "").splitlines()
        if not first_line:
            return "unknown"

        tokens = first_line[0].split()
        if len(tokens) >= 3:
            return tokens[2]
        return "unknown"
