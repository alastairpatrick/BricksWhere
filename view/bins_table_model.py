from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt


class BinsTableModel(QAbstractTableModel):
    PartNumCol = 0
    BinNumCol = 1
    RemarkCol = 2

    def __init__(self, vm, parent=None):
        super().__init__(parent)
        self._vm = vm
        self._rows = []

    def load(self, order_by: str = "part_num", descending: bool = False):
        self.beginResetModel()
        self._rows = self._vm.list_user_part_bins(order_by, descending)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return 3

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole or orientation != Qt.Horizontal:
            return None
        mapping = {
            self.PartNumCol: "Part Number",
            self.BinNumCol: "Bin Number",
            self.RemarkCol: "Remarks",
        }
        return mapping.get(section)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        col = index.column()
        if role in (Qt.DisplayRole, Qt.EditRole):
            if col == self.PartNumCol:
                return row["part_num"]
            if col == self.BinNumCol:
                return row["bin_num"]
            if col == self.RemarkCol:
                return row["remark"]
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable

    def setData(self, index, value, role=Qt.EditRole):
        if not index.isValid():
            return False
        row = self._rows[index.row()]
        col = index.column()
        part_num = row["part_num"]
        if col == self.PartNumCol:
            # update primary key
            new_part = value
            self._vm.update_part_num(part_num, new_part)
            row["part_num"] = new_part
        elif col == self.BinNumCol:
            self._vm.update_user_part_bin(part_num, value, row["remark"])
            row["bin_num"] = value
        elif col == self.RemarkCol:
            self._vm.update_user_part_bin(part_num, row["bin_num"], value)
            row["remark"] = value
        else:
            return False
        left = self.index(index.row(), index.column())
        right = self.index(index.row(), index.column())
        self.dataChanged.emit(left, right, [Qt.DisplayRole, Qt.EditRole])
        return True

    def sort(self, column: int, order: Qt.SortOrder = Qt.AscendingOrder):
        mapping = {
            self.PartNumCol: "part_num",
            self.BinNumCol: "bin_num",
            self.RemarkCol: "remark",
        }
        colname = mapping.get(column, "part_num")
        desc = order == Qt.DescendingOrder
        self.load(order_by=colname, descending=desc)
