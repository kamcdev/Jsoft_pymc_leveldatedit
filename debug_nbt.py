#!/usr/bin/env python3
"""Debug script to inspect NBT structure"""

import gzip
import os
import struct
import sys


def read_byte(data, pos):
    if pos >= len(data):
        raise Exception("EOF")
    return data[pos], pos + 1

def read_signed_byte(data, pos):
    b, pos = read_byte(data, pos)
    if b >= 128:
        return b - 256
    return b

def read_unsigned_byte(data, pos):
    return read_byte(data, pos)[0]

def read_int(data, pos):
    if pos + 4 > len(data):
        raise Exception("EOF")
    result = struct.unpack('>i', data[pos:pos + 4])[0]
    return result, pos + 4

def read_long(data, pos):
    if pos + 8 > len(data):
        raise Exception("EOF")
    result = struct.unpack('>q', data[pos:pos + 8])[0]
    return result, pos + 8

def read_short(data, pos):
    if pos + 2 > len(data):
        raise Exception("EOF")
    result = struct.unpack('>h', data[pos:pos + 2])[0]
    return result, pos + 2

def read_ushort(data, pos):
    if pos + 2 > len(data):
        raise Exception("EOF")
    result = struct.unpack('>H', data[pos:pos + 2])[0]
    return result, pos + 2

def read_string(data, pos):
    # Try signed short first
    length, pos = read_short(data, pos)
    if length < 0:
        # Try unsigned short
        pos -= 2
        length, pos = read_ushort(data, pos)

    if pos + length > len(data):
        raise Exception(f"String too long: {length} at pos {pos}")

    try:
        result = data[pos:pos + length].decode('utf-8')
    except:
        result = data[pos:pos + length].decode('latin-1', errors='replace')
    return result, pos + length

TAG_NAMES = {
    0: "TAG_End",
    1: "TAG_Byte",
    2: "TAG_Short",
    3: "TAG_Int",
    4: "TAG_Long",
    5: "TAG_Float",
    6: "TAG_Double",
    7: "TAG_Byte_Array",
    8: "TAG_String",
    9: "TAG_List",
    10: "TAG_Compound",
    11: "TAG_Int_Array",
    12: "TAG_Long_Array",
}

def read_tag(data, pos, indent=0):
    if pos >= len(data):
        return None, pos

    tag_type = data[pos]
    pos += 1

    if tag_type == 0:
        return None, pos

    name, pos = read_string(data, pos)

    prefix = "  " * indent

    try:
        if tag_type == 1:  # Byte
            value = read_signed_byte(data, pos)
            pos += 1
            print(f"{prefix}{TAG_NAMES[tag_type]}('{name}'): {value}")
        elif tag_type == 2:  # Short
            value, pos = read_short(data, pos)
            print(f"{prefix}{TAG_NAMES[tag_type]}('{name}'): {value}")
        elif tag_type == 3:  # Int
            value, pos = read_int(data, pos)
            print(f"{prefix}{TAG_NAMES[tag_type]}('{name}'): {value}")
        elif tag_type == 4:  # Long
            value, pos = read_long(data, pos)
            print(f"{prefix}{TAG_NAMES[tag_type]}('{name}'): {value}")
        elif tag_type == 5:  # Float
            value = struct.unpack('>f', data[pos:pos + 4])[0]
            pos += 4
            print(f"{prefix}{TAG_NAMES[tag_type]}('{name}'): {value}")
        elif tag_type == 6:  # Double
            value = struct.unpack('>d', data[pos:pos + 8])[0]
            pos += 8
            print(f"{prefix}{TAG_NAMES[tag_type]}('{name}'): {value}")
        elif tag_type == 7:  # Byte Array
            length, pos = read_int(data, pos)
            print(f"{prefix}{TAG_NAMES[tag_type]}('{name}'): [{length} bytes]")
            pos += length
        elif tag_type == 8:  # String
            value, pos = read_string(data, pos)
            print(f"{prefix}{TAG_NAMES[tag_type]}('{name}'): '{value}'")
        elif tag_type == 9:  # List
            list_type = data[pos]
            pos += 1
            length, pos = read_int(data, pos)
            print(f"{prefix}{TAG_NAMES[tag_type]}('{name}'): [{length} items of type {TAG_NAMES.get(list_type, list_type)}]")
            for i in range(min(length, 10)):  # Limit to 10 items
                if list_type == 1:
                    v = read_signed_byte(data, pos)
                    pos += 1
                    print(f"{prefix}  [{i}]: {v}")
                elif list_type == 2:
                    v, pos = read_short(data, pos)
                    print(f"{prefix}  [{i}]: {v}")
                elif list_type == 3:
                    v, pos = read_int(data, pos)
                    print(f"{prefix}  [{i}]: {v}")
                elif list_type == 4:
                    v, pos = read_long(data, pos)
                    print(f"{prefix}  [{i}]: {v}")
                elif list_type == 5:
                    v = struct.unpack('>f', data[pos:pos + 4])[0]
                    pos += 4
                    print(f"{prefix}  [{i}]: {v}")
                elif list_type == 6:
                    v = struct.unpack('>d', data[pos:pos + 8])[0]
                    pos += 8
                    print(f"{prefix}  [{i}]: {v}")
                elif list_type == 8:
                    v, pos = read_string(data, pos)
                    print(f"{prefix}  [{i}]: '{v}'")
                elif list_type == 10:
                    print(f"{prefix}  [{i}]: <compound>")
                else:
                    print(f"{prefix}  [{i}]: (type {list_type})")
            if length > 10:
                print(f"{prefix}  ... and {length - 10} more")
        elif tag_type == 10:  # Compound
            print(f"{prefix}{TAG_NAMES[tag_type]}('{name}'):")
            while pos < len(data):
                end_pos = read_tag(data, pos, indent + 1)[1]
                if end_pos == pos:
                    break
                pos = end_pos
                # Check if next is TAG_END
                if pos < len(data) and data[pos] == 0:
                    pos += 1
                    break
        elif tag_type == 11:  # Int Array
            length, pos = read_int(data, pos)
            print(f"{prefix}{TAG_NAMES[tag_type]}('{name}'): [{length} ints]")
            pos += length * 4
        elif tag_type == 12:  # Long Array
            length, pos = read_int(data, pos)
            print(f"{prefix}{TAG_NAMES[tag_type]}('{name}'): [{length} longs]")
            pos += length * 8
        else:
            print(f"{prefix}Unknown tag type {tag_type}")
    except Exception as e:
        print(f"{prefix}Error reading {name}: {e}")
        return name, pos

    return name, pos


def main():
    file_path = input("请输入level.dat文件路径: ").strip()

    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        return

    with open(file_path, 'rb') as f:
        data = f.read()

    print(f"文件大小: {len(data)} bytes")
    print(f"前20字节: {data[:20].hex()}")

    # Try gzip decompress
    original_data = data
    try:
        data = gzip.decompress(data)
        print("成功解压gzip")
        print(f"解压后大小: {len(data)} bytes")
    except Exception as e:
        print(f"未使用gzip压缩或解压失败: {e}")
        data = original_data

    print("\n=== NBT结构 ===")
    pos = 0
    try:
        while pos < len(data):
            name, pos = read_tag(data, pos)
            if name is None and pos >= len(data):
                break
            if pos == 0:
                break
    except Exception as e:
        print(f"解析错误: {e}")
        print(f"当前位置: {pos}, 数据长度: {len(data)}")


if __name__ == "__main__":
    main()
