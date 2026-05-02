#!/usr/bin/env python3
"""
MCLevelEdit - Minecraft Level.dat Parser & Editor (GUI Version)
"""

import gzip
import json
import os
import struct

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
APP_ICON_PATH = os.path.join(SCRIPT_DIR, 'pymc.ico')
from datetime import datetime
from typing import Any, Dict, Optional

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QLabel, QScrollArea,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QFileDialog, QDialog, QStyledItemDelegate
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QIntValidator, QDoubleValidator, QIcon


class NBTParser:
    TAG_END = 0
    TAG_BYTE = 1
    TAG_SHORT = 2
    TAG_INT = 3
    TAG_LONG = 4
    TAG_FLOAT = 5
    TAG_DOUBLE = 6
    TAG_BYTE_ARRAY = 7
    TAG_STRING = 8
    TAG_LIST = 9
    TAG_COMPOUND = 10
    TAG_INT_ARRAY = 11
    TAG_LONG_ARRAY = 12

    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0
        self.len = len(data)

    def read_byte(self) -> int:
        if self.pos >= self.len:
            raise Exception("EOF")
        result = self.data[self.pos]
        self.pos += 1
        return result

    def read_signed_byte(self) -> int:
        b = self.read_byte()
        if b >= 128:
            return b - 256
        return b

    def read_unsigned_byte(self) -> int:
        return self.read_byte()

    def read_int(self) -> int:
        if self.pos + 4 > self.len:
            raise Exception("EOF")
        result = struct.unpack('>i', self.data[self.pos:self.pos + 4])[0]
        self.pos += 4
        return result

    def read_long(self) -> int:
        if self.pos + 8 > self.len:
            raise Exception("EOF")
        result = struct.unpack('>q', self.data[self.pos:self.pos + 8])[0]
        self.pos += 8
        return result

    def read_float(self) -> float:
        if self.pos + 4 > self.len:
            raise Exception("EOF")
        result = struct.unpack('>f', self.data[self.pos:self.pos + 4])[0]
        self.pos += 4
        return result

    def read_double(self) -> float:
        if self.pos + 8 > self.len:
            raise Exception("EOF")
        result = struct.unpack('>d', self.data[self.pos:self.pos + 8])[0]
        self.pos += 8
        return result

    def read_short(self) -> int:
        if self.pos + 2 > self.len:
            raise Exception("EOF")
        result = struct.unpack('>h', self.data[self.pos:self.pos + 2])[0]
        self.pos += 2
        return result

    def read_unsigned_short(self) -> int:
        if self.pos + 2 > self.len:
            raise Exception("EOF")
        result = struct.unpack('>H', self.data[self.pos:self.pos + 2])[0]
        self.pos += 2
        return result

    def read_string(self) -> str:
        length = self.read_short()
        if length < 0:
            length = self.read_unsigned_short()

        if self.pos + length > self.len:
            raise Exception(f"String too long: {length} at pos {self.pos}")

        try:
            result = self.data[self.pos:self.pos + length].decode('utf-8')
        except:
            result = self.data[self.pos:self.pos + length].decode('latin-1', errors='replace')
        self.pos += length
        return result

    def read_named_tag(self) -> Optional[Dict[str, Any]]:
        tag_type = self.read_byte()

        if tag_type == self.TAG_END:
            return None

        name = self.read_string()
        value = self._read_tag_value(tag_type)

        return {'name': name, 'type': tag_type, 'value': value}

    def _read_tag_value(self, tag_type: int) -> Any:
        switch = {
            self.TAG_BYTE: self.read_signed_byte,
            self.TAG_SHORT: self.read_short,
            self.TAG_INT: self.read_int,
            self.TAG_LONG: self.read_long,
            self.TAG_FLOAT: self.read_float,
            self.TAG_DOUBLE: self.read_double,
            self.TAG_BYTE_ARRAY: self._read_byte_array,
            self.TAG_STRING: self.read_string,
            self.TAG_LIST: self._read_list,
            self.TAG_COMPOUND: self._read_compound,
            self.TAG_INT_ARRAY: self._read_int_array,
            self.TAG_LONG_ARRAY: self._read_long_array,
        }
        reader = switch.get(tag_type)
        if reader:
            return reader()
        return None

    def _read_byte_array(self) -> bytes:
        length = self.read_int()
        if self.pos + length > self.len:
            raise Exception("EOF")
        result = self.data[self.pos:self.pos + length]
        self.pos += length
        return result

    def _read_list(self) -> list:
        tag_type = self.read_byte()
        length = self.read_int()
        result = []
        for _ in range(length):
            value = self._read_tag_value(tag_type)
            result.append(value)
        return result

    def _read_compound(self) -> dict:
        result = {}
        while True:
            tag = self.read_named_tag()
            if tag is None:
                break
            result[tag['name']] = {'type': tag['type'], 'value': tag['value']}
        return result

    def _read_int_array(self) -> list:
        length = self.read_int()
        result = []
        for _ in range(length):
            result.append(self.read_int())
        return result

    def _read_long_array(self) -> list:
        length = self.read_int()
        result = []
        for _ in range(length):
            result.append(self.read_long())
        return result

    def parse(self) -> dict:
        tag_type = self.read_byte()

        name = ""
        if tag_type != self.TAG_END:
            try:
                name = self.read_string()
            except:
                pass

        if tag_type == self.TAG_COMPOUND:
            return self._read_compound()
        elif tag_type == self.TAG_STRING:
            return self.read_string()
        elif tag_type == self.TAG_INT:
            return self.read_int()
        elif tag_type == self.TAG_LONG:
            return self.read_long()
        else:
            raise ValueError(f"Unexpected tag type at root: {tag_type}")

    def write(self, data: Any, name: str = "") -> bytes:
        result = b""
        result += self._write_tag(self.TAG_COMPOUND, name, data)
        return result

    def _write_tag(self, tag_type: int, name: str, value: Any) -> bytes:
        result = bytes([tag_type])
        result += self._write_string(name)
        result += self._write_tag_value(tag_type, value)
        return result

    def _write_tag_value(self, tag_type: int, value: Any) -> bytes:
        if tag_type == self.TAG_END:
            return b""
        elif tag_type == self.TAG_BYTE:
            return self._write_byte(value)
        elif tag_type == self.TAG_SHORT:
            return self._write_short(value)
        elif tag_type == self.TAG_INT:
            return self._write_int(value)
        elif tag_type == self.TAG_LONG:
            return self._write_long(value)
        elif tag_type == self.TAG_FLOAT:
            return self._write_float(value)
        elif tag_type == self.TAG_DOUBLE:
            return self._write_double(value)
        elif tag_type == self.TAG_BYTE_ARRAY:
            return self._write_byte_array(value)
        elif tag_type == self.TAG_STRING:
            return self._write_string(value)
        elif tag_type == self.TAG_LIST:
            return self._write_list(value)
        elif tag_type == self.TAG_COMPOUND:
            return self._write_compound(value)
        elif tag_type == self.TAG_INT_ARRAY:
            return self._write_int_array(value)
        elif tag_type == self.TAG_LONG_ARRAY:
            return self._write_long_array(value)
        return b""

    def _write_byte(self, value: Any) -> bytes:
        if isinstance(value, bool):
            value = 1 if value else 0
        return bytes([int(value) & 0xFF])

    def _write_short(self, value: Any) -> bytes:
        return struct.pack('>h', int(value))

    def _write_int(self, value: Any) -> bytes:
        return struct.pack('>i', int(value))

    def _write_long(self, value: Any) -> bytes:
        return struct.pack('>q', int(value))

    def _write_float(self, value: Any) -> bytes:
        return struct.pack('>f', float(value))

    def _write_double(self, value: Any) -> bytes:
        return struct.pack('>d', float(value))

    def _write_string(self, value: Any) -> bytes:
        if not isinstance(value, str):
            value = str(value)
        encoded = value.encode('utf-8')
        return struct.pack('>h', len(encoded)) + encoded

    def _write_byte_array(self, value: Any) -> bytes:
        if isinstance(value, bytes):
            data = value
        elif isinstance(value, (list, tuple)):
            data = bytes(value)
        else:
            data = bytes(str(value), 'utf-8')
        return struct.pack('>i', len(data)) + data

    def _write_list(self, value: Any) -> bytes:
        if not isinstance(value, (list, tuple)):
            value = [value]

        if len(value) == 0:
            return bytes([self.TAG_END]) + struct.pack('>i', 0)

        first_type = self._get_value_type(value[0])
        result = bytes([first_type])
        result += struct.pack('>i', len(value))

        for item in value:
            result += self._write_tag_value(first_type, item)

        return result

    def _write_compound(self, value: Any) -> bytes:
        if not isinstance(value, dict):
            value = {'value': value}

        result = b""
        for key, val in value.items():
            if isinstance(val, dict) and 'type' in val and 'value' in val:
                tag_type = val['type']
                tag_value = val['value']
            else:
                tag_type = self._get_value_type(val)
                tag_value = val

            if tag_type != self.TAG_END:
                result += self._write_tag(tag_type, key, tag_value)

        result += bytes([self.TAG_END])
        return result

    def _write_int_array(self, value: Any) -> bytes:
        if not isinstance(value, (list, tuple)):
            value = [value]

        result = struct.pack('>i', len(value))
        for item in value:
            result += self._write_int(item)
        return result

    def _write_long_array(self, value: Any) -> bytes:
        if not isinstance(value, (list, tuple)):
            value = [value]

        result = struct.pack('>i', len(value))
        for item in value:
            result += self._write_long(item)
        return result

    def _get_value_type(self, value: Any) -> int:
        if value is None:
            return self.TAG_END
        elif isinstance(value, bool):
            return self.TAG_BYTE
        elif isinstance(value, int):
            if -128 <= value <= 127:
                return self.TAG_BYTE
            elif -32768 <= value <= 32767:
                return self.TAG_SHORT
            elif -2147483648 <= value <= 2147483647:
                return self.TAG_INT
            else:
                return self.TAG_LONG
        elif isinstance(value, float):
            return self.TAG_FLOAT
        elif isinstance(value, str):
            return self.TAG_STRING
        elif isinstance(value, bytes):
            return self.TAG_BYTE_ARRAY
        elif isinstance(value, (list, tuple)):
            if len(value) > 0:
                first = value[0]
                if isinstance(first, int):
                    return self.TAG_INT_ARRAY
                elif isinstance(first, str):
                    return self.TAG_LIST
                else:
                    return self.TAG_LIST
            return self.TAG_LIST
        elif isinstance(value, dict):
            return self.TAG_COMPOUND
        return self.TAG_STRING


def write_nbt_gzip(data: Any, name: str = "") -> bytes:
    parser = NBTParser(b"")
    nbt_bytes = parser.write(data, name)
    return gzip.compress(nbt_bytes, compresslevel=9)


def save_level_dat(file_path: str, nbt_data: dict) -> bool:
    try:
        wrapper = {'Data': {'type': NBTParser.TAG_COMPOUND, 'value': nbt_data}}
        compressed = write_nbt_gzip(wrapper, "")

        with open(file_path, 'wb') as f:
            f.write(compressed)
        return True
    except Exception as e:
        print(f"保存失败: {e}")
        return False


def read_level_dat(file_path: str) -> Optional[dict]:
    if not os.path.exists(file_path):
        return None

    try:
        with open(file_path, 'rb') as f:
            data = f.read()

        if len(data) < 2:
            return None

        try:
            data = gzip.decompress(data)
        except Exception:
            pass

        parser = NBTParser(data)
        nbt_data = parser.parse()

        if isinstance(nbt_data, dict):
            if 'Data' in nbt_data:
                data_val = nbt_data['Data']
                if isinstance(data_val, dict):
                    if 'value' in data_val:
                        return data_val['value']
                    return data_val
            return nbt_data

        return nbt_data

    except:
        return None


def get_game_type_name(game_type: int) -> str:
    game_types = {
        0: "生存",
        1: "创造",
        2: "冒险",
        3: "观察"
    }
    return game_types.get(game_type, f"未知 ({game_type})")


def get_difficulty_name(difficulty: int) -> str:
    difficulties = {
        0: "和平",
        1: "简单",
        2: "普通",
        3: "困难"
    }
    return difficulties.get(difficulty, f"未知 ({difficulty})")


def format_timestamp(timestamp: int) -> str:
    if timestamp == 0:
        return "未知"
    try:
        dt = datetime.fromtimestamp(timestamp / 1000.0)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return str(timestamp)


def get_nested_value(nbt_data: dict, *keys) -> Any:
    current = nbt_data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
            if current and isinstance(current, dict) and 'value' in current:
                current = current['value']
        else:
            return None
    return current


def flatten_nbt(data: dict, prefix: str = "") -> dict:
    result = {}

    for key, val in data.items():
        full_key = f"{prefix}{key}" if prefix else key

        if isinstance(val, dict):
            if 'type' in val and 'value' in val:
                tag_type = val['type']
                tag_value = val['value']

                if tag_type == NBTParser.TAG_COMPOUND:
                    result.update(flatten_nbt(tag_value, f"{full_key}."))
                elif tag_type == NBTParser.TAG_LIST:
                    result[full_key] = str(tag_value)
                else:
                    result[full_key] = tag_value
            else:
                result.update(flatten_nbt(val, f"{full_key}."))
        else:
            result[full_key] = val

    return result


def load_translations() -> dict:
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        translate_file = os.path.join(script_dir, 'key_translate.json')
        if os.path.exists(translate_file):
            with open(translate_file, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {}


TRANSLATIONS = load_translations()


def get_translation(key: str) -> str:
    last_key = key.split('.')[-1]
    game_rule_match = key.split('.')
    if len(game_rule_match) >= 2 and game_rule_match[0] == 'GameRules':
        game_rule_key = "gameRule." + game_rule_match[1]
        if game_rule_key in TRANSLATIONS:
            return TRANSLATIONS[game_rule_key]

    if key in TRANSLATIONS:
        return TRANSLATIONS[key]
    if last_key in TRANSLATIONS:
        return TRANSLATIONS[last_key]
    return ""


class FileSelectWindow(QDialog):
    fileSelected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowIcon(QIcon(APP_ICON_PATH))
        self.setWindowTitle("MCLevelEdit - 选择文件")
        self.setMinimumWidth(500)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        label = QLabel("请输入 level.dat 文件路径:")
        layout.addWidget(label)

        path_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("请输入文件路径...")
        path_layout.addWidget(self.path_input)

        browse_btn = QPushButton("定位")
        browse_btn.clicked.connect(self.browse_file)
        path_layout.addWidget(browse_btn)

        layout.addLayout(path_layout)

        open_btn = QPushButton("打开")
        open_btn.clicked.connect(self.open_file)
        layout.addWidget(open_btn)

        self.setLayout(layout)

    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 level.dat 文件",
            "",
            "Level Dat Files (*.dat);;All Files (*)"
        )
        if file_path:
            self.path_input.setText(file_path)

    def open_file(self):
        file_path = self.path_input.text().strip()
        if not file_path:
            QMessageBox.warning(self, "警告", "请输入文件路径")
            return

        if not os.path.exists(file_path):
            QMessageBox.warning(self, "警告", "文件不存在")
            return

        self.fileSelected.emit(file_path)
        self.accept()


class JsonSelectWindow(QDialog):
    fileSelected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowIcon(QIcon(APP_ICON_PATH))
        self.setWindowTitle("MCLevelEdit - 选择文件")
        self.setMinimumWidth(500)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        label = QLabel("请输入 原数据json 文件路径:")
        layout.addWidget(label)

        path_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("请输入文件路径...")
        path_layout.addWidget(self.path_input)

        browse_btn = QPushButton("定位")
        browse_btn.clicked.connect(self.browse_file)
        path_layout.addWidget(browse_btn)

        layout.addLayout(path_layout)

        open_btn = QPushButton("打开")
        open_btn.clicked.connect(self.open_file)
        layout.addWidget(open_btn)

        self.setLayout(layout)

    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 原数据json 文件",
            "",
            "JSON Files (*.json);;All Files (*)"
        )
        if file_path:
            self.path_input.setText(file_path)

    def open_file(self):
        file_path = self.path_input.text().strip()
        if not file_path:
            QMessageBox.warning(self, "警告", "请输入文件路径")
            return

        if not os.path.exists(file_path):
            QMessageBox.warning(self, "警告", "文件不存在")
            return

        self.fileSelected.emit(file_path)
        self.accept()


class ParseModeWindow(QDialog):
    parseModeSelected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowIcon(QIcon(APP_ICON_PATH))
        self.setWindowTitle("选择解析方式")
        self.setMinimumWidth(300)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        label = QLabel("请选择解析方式:")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        dat_btn = QPushButton("从leveldat读取")
        dat_btn.clicked.connect(lambda: self.select_mode("dat"))
        layout.addWidget(dat_btn)

        json_btn = QPushButton("从原数据读取")
        json_btn.clicked.connect(lambda: self.select_mode("json"))
        layout.addWidget(json_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)

        self.setLayout(layout)

    def select_mode(self, mode: str):
        self.parseModeSelected.emit(mode)
        self.accept()


class ModeSelectWindow(QDialog):
    modeSelected = Signal(str)
    exportRequested = Signal(dict)

    def __init__(self, nbt_data: dict, file_path: str, parent=None):
        self.nbt_data = nbt_data
        self.file_path = file_path
        super().__init__(parent)
        self.setWindowIcon(QIcon(APP_ICON_PATH))
        self.setWindowTitle(f"选择模式：{file_path}")
        self.setMinimumWidth(300)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        label = QLabel("请选择操作模式:")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        read_btn = QPushButton("读取模式")
        read_btn.clicked.connect(lambda: self.select_mode("read"))
        layout.addWidget(read_btn)

        edit_btn = QPushButton("编辑模式")
        edit_btn.clicked.connect(lambda: self.select_mode("edit"))
        layout.addWidget(edit_btn)

        export_btn = QPushButton("导出原数据")
        export_btn.clicked.connect(self.export_data)
        layout.addWidget(export_btn)

        self.setLayout(layout)

    def select_mode(self, mode: str):
        self.modeSelected.emit(mode)
        self.accept()

    def export_data(self):
        import json
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"导出原数据 - {self.file_path}",
            "",
            "JSON Files (*.json);;All Files (*)"
        )
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.nbt_data, f, ensure_ascii=False, indent=2)
                QMessageBox.information(self, "提示", f"导出成功: {file_path}")
                self.accept()
                QTimer.singleShot(0, self.parent().open_mode_select)
            except Exception as e:
                QMessageBox.warning(self, "错误", f"导出失败: {e}")


class ReadModeWindow(QDialog):
    backRequested = Signal()

    def __init__(self, nbt_data: dict, file_path: str, parent=None):
        self.nbt_data = nbt_data
        self.file_path = file_path
        super().__init__(parent)
        self.setWindowIcon(QIcon(APP_ICON_PATH))
        self.setWindowTitle(f"读取模式：{file_path}")
        self.setMinimumSize(600, 400)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMinMaxButtonsHint)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()

        def get_value(key: str, default: Any = None) -> Any:
            if isinstance(self.nbt_data.get(key), dict):
                return self.nbt_data[key].get('value', default)
            return self.nbt_data.get(key, default)

        level_name = get_value('LevelName', '未知')
        scroll_layout.addWidget(QLabel(f"世界名称: {level_name}"))

        random_seed = get_value('RandomSeed', 0)
        if random_seed == 0:
            world_gen_settings = get_value('WorldGenSettings')
            if world_gen_settings:
                random_seed = get_nested_value(world_gen_settings, 'seed') or 0
        scroll_layout.addWidget(QLabel(f"世界种子: {random_seed}"))

        spawn_x = get_value('SpawnX', 0)
        spawn_y = get_value('SpawnY', 0)
        spawn_z = get_value('SpawnZ', 0)
        scroll_layout.addWidget(QLabel(f"出生点: ({spawn_x}, {spawn_y}, {spawn_z})"))

        difficulty = get_value('Difficulty', 2)
        scroll_layout.addWidget(QLabel(f"难度: {get_difficulty_name(difficulty)}"))

        game_type = get_value('GameType', 0)
        scroll_layout.addWidget(QLabel(f"游戏模式: {get_game_type_name(game_type)}"))

        hardcore = get_value('Hardcore', False)
        scroll_layout.addWidget(QLabel(f"极限模式: {'是' if hardcore else '否'}"))

        last_played = get_value('LastPlayed', 0)
        scroll_layout.addWidget(QLabel(f"最后游玩: {format_timestamp(last_played)}"))

        version = get_value('Version')
        if version:
            version_name = '未知'
            if isinstance(version, dict):
                version_value = version.get('value', version)
                if isinstance(version_value, dict):
                    name_val = version_value.get('Name')
                    if isinstance(name_val, dict):
                        version_name = name_val.get('value', '未知')
                    elif isinstance(name_val, str):
                        version_name = name_val
            elif isinstance(version, str):
                version_name = version
            scroll_layout.addWidget(QLabel(f"版本: {version_name}"))

        game_rules = get_value('GameRules')
        if game_rules:
            if isinstance(game_rules, dict) and 'value' in game_rules:
                game_rules = game_rules['value']
            if isinstance(game_rules, dict):
                for rule_name, rule_value in sorted(game_rules.items()):
                    if isinstance(rule_value, dict):
                        rule_value = rule_value.get('value', '')
                    scroll_layout.addWidget(QLabel(f"游戏规则 {rule_name}: {rule_value}"))

        flat_data = flatten_nbt(self.nbt_data)
        for key, value in sorted(flat_data.items()):
            scroll_layout.addWidget(QLabel(f"{key}: {value}"))

        scroll_widget.setLayout(scroll_layout)
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        back_btn = QPushButton("返回")
        back_btn.clicked.connect(self.go_back)
        layout.addWidget(back_btn)

        self.setLayout(layout)

    def go_back(self):
        self.backRequested.emit()
        self.accept()


class InputValidatorDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_table = parent

    def createEditor(self, parent, option, index):
        if index.column() != 2:
            return super().createEditor(parent, option, index)
        return super().createEditor(parent, option, index)


class EditModeWindow(QDialog):
    backRequested = Signal()

    def __init__(self, nbt_data: dict, file_path: str, parent=None):
        self.nbt_data = nbt_data
        self.file_path = file_path
        self.original_data = flatten_nbt(nbt_data)
        self.value_types = self._get_value_types()
        super().__init__(parent)
        self.setWindowIcon(QIcon(APP_ICON_PATH))
        self.setWindowTitle(f"编辑模式：{file_path}")
        self.setMinimumSize(800, 500)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMinMaxButtonsHint)
        self.init_ui()

        if parent and hasattr(parent, 'translation_notice_shown') and not parent.translation_notice_shown:
            parent.translation_notice_shown = True
            QTimer.singleShot(100, self.show_translation_notice)

    def show_translation_notice(self):
        QMessageBox.information(
            self,
            "关于翻译",
            "大部分翻译使用wiki中记载的翻译，但有部分翻译使用了机翻，请理性看待\n"
            "欢迎在本项目开源仓库中提交更合适的翻译进行代替"
        )

    def _get_value_types(self):
        types = {}
        for key, val in self.nbt_data.items():
            if isinstance(val, dict) and 'type' in val and 'value' in val:
                types[key] = val['type']
        return types

    def _get_actual_value_type(self, key, default_value):
        if key in self.value_types:
            return self.value_types[key]

        keys = key.split('.')
        current = self.nbt_data
        for k in keys[:-1]:
            if k in current:
                if isinstance(current[k], dict) and 'value' in current[k]:
                    current = current[k]['value']
                elif isinstance(current[k], dict):
                    current = current[k]
                else:
                    break
            else:
                break

        last_key = keys[-1]
        if last_key in current:
            val = current[last_key]
            if isinstance(val, dict) and 'type' in val:
                return val['type']

        if isinstance(default_value, bool):
            return NBTParser.TAG_BYTE
        elif isinstance(default_value, int):
            if -128 <= default_value <= 127:
                return NBTParser.TAG_BYTE
            elif -32768 <= default_value <= 32767:
                return NBTParser.TAG_SHORT
            return NBTParser.TAG_INT
        elif isinstance(default_value, float):
            return NBTParser.TAG_FLOAT
        elif isinstance(default_value, str):
            if default_value.startswith('['):
                return NBTParser.TAG_INT_ARRAY
            return NBTParser.TAG_STRING
        return NBTParser.TAG_STRING

    def init_ui(self):
        layout = QVBoxLayout()

        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("搜索:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索")
        self.search_input.setMinimumWidth(200)
        self.search_input.textChanged.connect(self.on_search_changed)
        search_layout.addWidget(self.search_input)

        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self.on_refresh_clicked)
        search_layout.addWidget(refresh_btn)

        search_layout.addStretch()
        layout.addLayout(search_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["键", "翻译", "值"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        self.all_data = []
        flat_data = flatten_nbt(self.nbt_data)
        for key, value in sorted(flat_data.items()):
            translation = get_translation(key)
            value_type = self._get_actual_value_type(key, value)
            self.all_data.append({
                'key': key,
                'translation': translation,
                'value': str(value),
                'value_type': value_type,
                'original_value': value
            })

        self.populate_table(self.all_data)

        scroll.setWidget(self.table)
        layout.addWidget(scroll)

        btn_layout = QHBoxLayout()

        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.save_data)
        btn_layout.addWidget(save_btn)

        output_btn = QPushButton("输出")
        output_btn.clicked.connect(self.output_data)
        btn_layout.addWidget(output_btn)

        back_btn = QPushButton("返回")
        back_btn.clicked.connect(self.go_back)
        btn_layout.addWidget(back_btn)

        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def on_search_changed(self, text):
        self.sync_table_to_data()

        if not text:
            self.populate_table(self.all_data)
            return

        search_text = text.lower()
        filtered = []
        for item in self.all_data:
            if (search_text in item['key'].lower() or
                search_text in item['translation'].lower() or
                search_text in item['value'].lower()):
                filtered.append(item)

        self.populate_table(filtered)

    def on_refresh_clicked(self):
        msg_box = QMessageBox(self)
        msg_box.setWindowIcon(QIcon(APP_ICON_PATH))
        msg_box.setWindowTitle("刷新")
        msg_box.setText("是否保存当前编辑？")
        msg_box.setIcon(QMessageBox.Icon.Question)

        save_btn = msg_box.addButton("保存", QMessageBox.ButtonRole.YesRole)
        discard_btn = msg_box.addButton("放弃", QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn = msg_box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        msg_box.setDefaultButton(cancel_btn)

        msg_box.exec()

        if msg_box.clickedButton() == save_btn:
            self.save_data()
            self.accept()
            QTimer.singleShot(100, lambda: self.parent().open_edit_mode())
        elif msg_box.clickedButton() == discard_btn:
            self.accept()
            QTimer.singleShot(100, lambda: self.parent().open_edit_mode())

    def sync_table_to_data(self):
        for i in range(self.table.rowCount()):
            key = self.table.item(i, 0).text()
            value = self.table.item(i, 2).text()

            for item in self.all_data:
                if item['key'] == key:
                    item['value'] = value
                    break

    def populate_table(self, data):
        self.table.setRowCount(len(data))

        for i, item in enumerate(data):
            key_item = QTableWidgetItem(item['key'])
            key_item.setFlags(key_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 0, key_item)

            trans_item = QTableWidgetItem(item['translation'])
            trans_item.setFlags(trans_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 1, trans_item)

            value_type = item['value_type']
            value_item = QTableWidgetItem(item['value'])

            if value_type in (NBTParser.TAG_BYTE_ARRAY, NBTParser.TAG_INT_ARRAY, NBTParser.TAG_LONG_ARRAY, NBTParser.TAG_LIST):
                value_item.setFlags(value_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                value_item.setToolTip("数组类型，不可编辑")
            elif value_type == NBTParser.TAG_BYTE:
                if isinstance(item['original_value'], bool) or (isinstance(item['original_value'], int) and item['original_value'] in (0, 1)):
                    value_item.setToolTip("布尔值: true/false")
                else:
                    value_item.setToolTip("整数")
            elif value_type in (NBTParser.TAG_SHORT, NBTParser.TAG_INT, NBTParser.TAG_LONG):
                value_item.setToolTip("整数")
            elif value_type in (NBTParser.TAG_FLOAT, NBTParser.TAG_DOUBLE):
                value_item.setToolTip("小数")
            elif value_type == NBTParser.TAG_STRING:
                value_item.setToolTip("字符串")

            value_item.setData(Qt.UserRole, value_type)
            self.table.setItem(i, 2, value_item)

        self.table.setItemDelegateForColumn(2, InputValidatorDelegate(self.table))

    def save_data(self):
        msg_box = QMessageBox(self)
        msg_box.setWindowIcon(QIcon(APP_ICON_PATH))
        msg_box.setWindowTitle("确认保存")
        msg_box.setText("是否确认保存？编辑数据可能会导致存档损坏")
        msg_box.setIcon(QMessageBox.Icon.Question)

        yes_btn = msg_box.addButton("继续", QMessageBox.ButtonRole.YesRole)
        no_btn = msg_box.addButton("取消", QMessageBox.ButtonRole.NoRole)
        msg_box.setDefaultButton(no_btn)

        msg_box.exec()

        if msg_box.clickedButton() == yes_btn:
            self.sync_table_to_data()
            self.update_nbt_data()

            try:
                if os.path.exists(self.file_path):
                    os.remove(self.file_path)

                if save_level_dat(self.file_path, self.nbt_data):
                    QMessageBox.information(self, "提示", f"保存成功: {self.file_path}")
                else:
                    QMessageBox.warning(self, "错误", "保存失败")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"保存失败: {e}")

    def output_data(self):
        self.sync_table_to_data()
        self.update_nbt_data()

        dialog = OutputModeWindow(self.file_path, self)
        dialog.outputModeSelected.connect(lambda mode: self.do_output(mode))
        dialog.exec()

    def do_output(self, mode: str):
        if mode == "json":
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                f"导出原数据 - {self.file_path}",
                "",
                "JSON Files (*.json);;All Files (*)"
            )

            if file_path:
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(self.nbt_data, f, ensure_ascii=False, indent=2)
                    QMessageBox.information(self, "提示", f"导出成功: {file_path}")
                except Exception as e:
                    QMessageBox.warning(self, "错误", f"导出失败: {e}")
        elif mode == "dat":
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                f"保存 level.dat - {self.file_path}",
                "",
                "Level Dat Files (*.dat);;All Files (*)"
            )

            if file_path:
                if save_level_dat(file_path, self.nbt_data):
                    QMessageBox.information(self, "提示", f"保存成功: {file_path}")
                else:
                    QMessageBox.warning(self, "错误", "保存失败")

    def update_nbt_data(self):
        for item in self.all_data:
            key = item['key']
            value_str = item['value']
            original_value = item['original_value']
            value_type = item['value_type']

            if value_type in (NBTParser.TAG_BYTE_ARRAY, NBTParser.TAG_INT_ARRAY, NBTParser.TAG_LONG_ARRAY):
                continue

            if value_type == NBTParser.TAG_BYTE:
                if isinstance(original_value, bool) or (isinstance(original_value, int) and original_value in (0, 1)):
                    new_value = value_str.lower() in ('true', '1', 'yes')
                else:
                    try:
                        new_value = int(value_str)
                    except:
                        new_value = original_value
            elif value_type in (NBTParser.TAG_SHORT, NBTParser.TAG_INT, NBTParser.TAG_LONG):
                try:
                    new_value = int(value_str)
                except:
                    new_value = original_value
            elif value_type in (NBTParser.TAG_FLOAT, NBTParser.TAG_DOUBLE):
                try:
                    new_value = float(value_str)
                except:
                    new_value = original_value
            elif value_type == NBTParser.TAG_LIST:
                new_value = value_str
            else:
                if isinstance(original_value, bool):
                    new_value = value_str.lower() in ('true', '1', 'yes')
                elif isinstance(original_value, int):
                    try:
                        new_value = int(value_str)
                    except:
                        new_value = original_value
                elif isinstance(original_value, float):
                    try:
                        new_value = float(value_str)
                    except:
                        new_value = original_value
                elif isinstance(original_value, list):
                    new_value = value_str
                else:
                    new_value = value_str

            keys = key.split('.')
            current = self.nbt_data
            for k in keys[:-1]:
                if k in current:
                    if isinstance(current[k], dict) and 'value' in current[k]:
                        current[k] = current[k]['value']
                    current = current[k]

            last_key = keys[-1]
            if last_key in current:
                if isinstance(current[last_key], dict) and 'type' in current[last_key]:
                    current[last_key]['value'] = new_value
                else:
                    current[last_key] = new_value

    def go_back(self):
        self.backRequested.emit()
        self.accept()


class OutputModeWindow(QDialog):
    outputModeSelected = Signal(str)

    def __init__(self, file_path: str, parent=None):
        self.file_path = file_path
        super().__init__(parent)
        self.setWindowIcon(QIcon(APP_ICON_PATH))
        self.setWindowTitle(f"输出模式选择：{file_path}")
        self.setMinimumWidth(300)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        label = QLabel("请选择输出模式:")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        json_btn = QPushButton("原数据")
        json_btn.clicked.connect(lambda: self.select_mode("json"))
        layout.addWidget(json_btn)

        dat_btn = QPushButton("打包为leveldat")
        dat_btn.clicked.connect(lambda: self.select_mode("dat"))
        layout.addWidget(dat_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)

        self.setLayout(layout)

    def select_mode(self, mode: str):
        self.outputModeSelected.emit(mode)
        self.accept()


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon(APP_ICON_PATH))
        self.setWindowTitle("MCLevelEdit")
        self.setMinimumSize(400, 200)
        self.nbt_data = None
        self.file_path = None
        self.translation_notice_shown = False
        self.mode_select_window = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        label = QLabel("欢迎使用 MCLevelEdit")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        select_btn = QPushButton("选择文件")
        select_btn.clicked.connect(self.open_file_select)
        layout.addWidget(select_btn)

        quit_btn = QPushButton("退出")
        quit_btn.clicked.connect(self.close)
        layout.addWidget(quit_btn)

        self.setLayout(layout)

    def open_file_select(self):
        dialog = ParseModeWindow(self)
        dialog.parseModeSelected.connect(self.on_parse_mode_selected)
        dialog.exec()

    def on_parse_mode_selected(self, mode: str):
        if mode == "dat":
            file_dialog = FileSelectWindow(self)
            file_dialog.fileSelected.connect(self.on_file_selected)
            file_dialog.exec()
        elif mode == "json":
            json_dialog = JsonSelectWindow(self)
            json_dialog.fileSelected.connect(self.on_json_selected)
            json_dialog.exec()

    def on_json_selected(self, json_file_path: str):
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                self.nbt_data = json.load(f)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"无法读取原数据文件: {e}")
            return

        msg_box = QMessageBox(self)
        msg_box.setWindowIcon(QIcon(APP_ICON_PATH))
        msg_box.setWindowTitle("提示")
        msg_box.setText("需先打包为leveldat，是否继续")
        msg_box.setIcon(QMessageBox.Icon.Question)

        continue_btn = msg_box.addButton("继续", QMessageBox.ButtonRole.YesRole)
        cancel_btn = msg_box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        msg_box.setDefaultButton(cancel_btn)

        msg_box.exec()

        if msg_box.clickedButton() == continue_btn:
            export_path, _ = QFileDialog.getSaveFileName(
                self,
                "保存 level.dat",
                "",
                "Level Dat Files (*.dat);;All Files (*)"
            )

            if export_path:
                if save_level_dat(export_path, self.nbt_data):
                    self.file_path = export_path
                    QTimer.singleShot(0, self.open_mode_select)
                else:
                    QMessageBox.warning(self, "错误", "保存失败")

    def on_file_selected(self, file_path: str):
        self.file_path = file_path
        self.nbt_data = read_level_dat(file_path)

        if self.nbt_data is None:
            QMessageBox.warning(self, "错误", "无法读取 level.dat 文件")
            return

        self.open_mode_select()

    def open_mode_select(self):
        if self.mode_select_window is not None and self.mode_select_window.isVisible():
            self.mode_select_window.close()
        self.mode_select_window = ModeSelectWindow(self.nbt_data, self.file_path, self)
        self.mode_select_window.modeSelected.connect(self.on_mode_selected)
        self.mode_select_window.exec()

    def on_mode_selected(self, mode: str):
        if mode == "read":
            QTimer.singleShot(0, self.open_read_mode)
        else:
            QTimer.singleShot(0, self.open_edit_mode)

    def open_read_mode(self):
        dialog = ReadModeWindow(self.nbt_data, self.file_path, self)
        dialog.exec()
        if dialog.result() == QDialog.DialogCode.Accepted:
            QTimer.singleShot(0, self.open_mode_select)

    def on_back_from_read(self):
        pass

    def open_edit_mode(self):
        dialog = EditModeWindow(self.nbt_data, self.file_path, self)
        dialog.exec()
        if dialog.result() == QDialog.DialogCode.Accepted:
            self.nbt_data = read_level_dat(self.file_path)
            QTimer.singleShot(0, self.open_mode_select)

    def on_back_from_edit(self):
        pass


def main():
    app = QApplication([])
    app.setWindowIcon(QIcon(APP_ICON_PATH))
    window = MainWindow()
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
