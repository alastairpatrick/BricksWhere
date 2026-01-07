from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QCheckBox


class BinRangeDialog(QDialog):
    """Dialog prompting for a start and end bin number and an "Include Images" option.

    Generate is disabled until both fields are non-empty and the end value
    sorts after the start value (ascending string order).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bin Range")
        self._build()

    def _build(self):
        v = QVBoxLayout(self)

        row = QHBoxLayout()
        row.addWidget(QLabel("Start Bin Number:"))
        self._start = QLineEdit()
        row.addWidget(self._start)
        v.addLayout(row)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("End Bin Number:"))
        self._end = QLineEdit()
        row2.addWidget(self._end)
        v.addLayout(row2)

        self._include_images = QCheckBox("Include Images")
        self._include_images.setChecked(False)
        v.addWidget(self._include_images)

        btns = QHBoxLayout()
        btns.addStretch()
        self._cancel = QPushButton("Cancel")
        self._generate = QPushButton("Generate")
        self._generate.setEnabled(False)
        btns.addWidget(self._cancel)
        btns.addWidget(self._generate)
        v.addLayout(btns)

        # connections
        self._start.textChanged.connect(self._update_generate_state)
        self._end.textChanged.connect(self._update_generate_state)
        self._cancel.clicked.connect(self.reject)
        # generate intentionally does nothing for now

    def _update_generate_state(self, _text=None):
        s = (self._start.text() or "").strip()
        e = (self._end.text() or "").strip()
        if not s or not e:
            self._generate.setEnabled(False)
            return
        # enable only if end sorts after start (ascending order)
        self._generate.setEnabled(e > s)

    @property
    def include_images(self):
        return self._include_images.isChecked()
