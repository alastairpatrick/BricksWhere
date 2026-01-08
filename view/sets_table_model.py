from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex


class SetsTableModel(QAbstractTableModel):
    """Table model for user_sets shown in the Sets tab.

    Columns: 0=set_num, 1=name, 2=quantity, 3=remark
    The model holds rows as list of dicts matching the SetsViewModel output.
    """

    # Column constants (class-level for easier access in tests)
    SetNumCol = 0
    NameCol = 1
    QuantityCol = 2
    RemarkCol = 3

    def __init__(self, sets_vm, parent=None):
        super().__init__(parent)
        self._vm = sets_vm
        self._rows = []

    def load(self, order_by="set_num", descending=False):
        try:
            self.beginResetModel()
            self._rows = list(self._vm.list_user_sets(order_by=order_by, descending=descending))
        finally:
            self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return 4

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        r = self._rows[index.row()]
        c = index.column()
        if role in (Qt.DisplayRole, Qt.EditRole):
            if c == self.SetNumCol:
                return r.get("set_num", "")
            if c == self.NameCol:
                return r.get("name", "")
            if c == self.QuantityCol:
                return str(r.get("quantity", 0))
            if c == self.RemarkCol:
                return r.get("remark", "")
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return ["Set Number", "Name", "Quantity", "Remark"][section]
        return super().headerData(section, orientation, role)

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        c = index.column()
        fl = Qt.ItemIsSelectable | Qt.ItemIsEnabled
        if c in (self.SetNumCol, self.QuantityCol, self.RemarkCol):
            fl |= Qt.ItemIsEditable
        return fl

    def setData(self, index, value, role=Qt.EditRole):
        if not index.isValid() or role != Qt.EditRole:
            return False
        row = index.row()
        col = index.column()
        old = self._rows[row]
        try:
            if col == self.SetNumCol:
                # change set_num -> delegate to VM update_set_num
                old_set = old.get("set_num")
                new_set = str(value)
                if new_set != old_set:
                    self._vm.update_set_num(old_set, new_set)
                    # update local cache and refresh name if available from VM
                    self._rows[row]["set_num"] = new_set
                    try:
                        all_rows = list(self._vm.list_user_sets())
                        name_map = {r["set_num"]: r.get("name", "") for r in all_rows}
                        self._rows[row]["name"] = name_map.get(new_set, self._rows[row].get("name", ""))
                    except Exception:
                        pass
                    topLeft = self.index(row, 0)
                    bottomRight = self.index(row, self.NameCol)
                    self.dataChanged.emit(topLeft, bottomRight, [Qt.DisplayRole])
                    return True
            elif col == self.QuantityCol:
                qty = int(value) if value != "" else 0
                self._vm.update_user_set(old.get("set_num"), qty, old.get("remark", ""))
                self._rows[row]["quantity"] = qty
                idx = self.index(row, self.QuantityCol)
                self.dataChanged.emit(idx, idx, [Qt.DisplayRole])
                return True
            elif col == self.RemarkCol:
                remark = str(value)
                self._vm.update_user_set(old.get("set_num"), old.get("quantity", 0), remark)
                self._rows[row]["remark"] = remark
                idx = self.index(row, self.RemarkCol)
                self.dataChanged.emit(idx, idx, [Qt.DisplayRole])
                return True
        except Exception:
            return False
        return False

    def sort(self, column, order):
        # simple in-memory sort
        reverse = order == Qt.DescendingOrder
        key = None
        if column == self.SetNumCol:
            from model.sorting import int_prefixed_key
            key = lambda r: int_prefixed_key(r.get("set_num", ""))
        elif column == self.NameCol:
            key = lambda r: r.get("name", "")
        elif column == self.QuantityCol:
            key = lambda r: r.get("quantity", 0)
        elif column == self.RemarkCol:
            key = lambda r: r.get("remark", "")
        if key:
            self.layoutAboutToBeChanged.emit()
            self._rows.sort(key=key, reverse=reverse)
            self.layoutChanged.emit()
