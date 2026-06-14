import csv
from typing import List, Tuple, Optional, Set
from datetime import datetime, timedelta
from .models import SupplierBillItem, ReceivingListItem, ValidationResult, ValidationError

BILL_REQUIRED_FIELDS = [
    'bill_no', 'item_code', 'item_name', 'quantity', 
    'unit_price', 'amount', 'bill_date', 'supplier_code', 'supplier_name'
]

RECEIVE_REQUIRED_FIELDS = [
    'receive_no', 'item_code', 'item_name', 'quantity',
    'unit_price', 'amount', 'receive_date', 'supplier_code',
    'supplier_name', 'purchase_order_no'
]

BILL_NUMERIC_FIELDS = ['quantity', 'unit_price', 'amount']
RECEIVE_NUMERIC_FIELDS = ['quantity', 'unit_price', 'amount']

def get_field_value(row: dict, field: str) -> Optional[str]:
    return row.get(field, '').strip() if row.get(field) else None

def validate_bill_with_required_fields(
    file_path: str, 
    custom_required_fields: List[str] = None
) -> ValidationResult:
    result = ValidationResult()
    required_fields = custom_required_fields or BILL_REQUIRED_FIELDS
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            
            missing_header_fields = [f for f in required_fields if f not in fieldnames]
            if missing_header_fields:
                result.errors.append(ValidationError(
                    row=0,
                    field="header",
                    value="",
                    error_type="MISSING_FIELD",
                    message=f"文件缺少必需字段: {', '.join(missing_header_fields)}"
                ))
                return result
            
            for row_idx, row in enumerate(reader, start=1):
                for field in required_fields:
                    value = get_field_value(row, field)
                    if value is None or value == '':
                        result.errors.append(ValidationError(
                            row=row_idx,
                            field=field,
                            value="",
                            error_type="EMPTY_FIELD",
                            message=f"字段 {field} 不能为空"
                        ))
                    elif field in BILL_NUMERIC_FIELDS:
                        try:
                            float(row[field])
                        except ValueError:
                            result.errors.append(ValidationError(
                                row=row_idx,
                                field=field,
                                value=row[field],
                                error_type="INVALID_NUMBER",
                                message=f"字段 {field} 必须是数字，当前值: {row[field]}"
                            ))
                
                if not result.errors or not any(e.row == row_idx for e in result.errors):
                    result.valid_rows.append(dict(row))
    except Exception as e:
        result.errors.append(ValidationError(
            row=0,
            field="file",
            value="",
            error_type="FILE_ERROR",
            message=f"无法读取文件: {str(e)}"
        ))
    
    return result

def validate_receiving_with_required_fields(
    file_path: str, 
    custom_required_fields: List[str] = None
) -> ValidationResult:
    result = ValidationResult()
    required_fields = custom_required_fields or RECEIVE_REQUIRED_FIELDS
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            
            missing_header_fields = [f for f in required_fields if f not in fieldnames]
            if missing_header_fields:
                result.errors.append(ValidationError(
                    row=0,
                    field="header",
                    value="",
                    error_type="MISSING_FIELD",
                    message=f"文件缺少必需字段: {', '.join(missing_header_fields)}"
                ))
                return result
            
            for row_idx, row in enumerate(reader, start=1):
                for field in required_fields:
                    value = get_field_value(row, field)
                    if value is None or value == '':
                        result.errors.append(ValidationError(
                            row=row_idx,
                            field=field,
                            value="",
                            error_type="EMPTY_FIELD",
                            message=f"字段 {field} 不能为空"
                        ))
                    elif field in RECEIVE_NUMERIC_FIELDS:
                        try:
                            float(row[field])
                        except ValueError:
                            result.errors.append(ValidationError(
                                row=row_idx,
                                field=field,
                                value=row[field],
                                error_type="INVALID_NUMBER",
                                message=f"字段 {field} 必须是数字，当前值: {row[field]}"
                            ))
                
                if not result.errors or not any(e.row == row_idx for e in result.errors):
                    result.valid_rows.append(dict(row))
    except Exception as e:
        result.errors.append(ValidationError(
            row=0,
            field="file",
            value="",
            error_type="FILE_ERROR",
            message=f"无法读取文件: {str(e)}"
        ))
    
    return result

def parse_date(date_str: str) -> Optional[datetime]:
    formats = ['%Y-%m-%d', '%Y/%m/%d', '%Y%m%d', '%d-%m-%Y', '%d/%m/%Y']
    date_str = date_str.strip()
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None

def check_date_offset(bill_date_str: str, receive_date_str: str, offset_days: int) -> Tuple[bool, str]:
    if offset_days == 0:
        return True, ""
    
    bill_date = parse_date(bill_date_str)
    receive_date = parse_date(receive_date_str)
    
    if bill_date is None or receive_date is None:
        return False, "日期格式无法解析"
    
    days_diff = abs((bill_date - receive_date).days)
    if days_diff <= abs(offset_days):
        return True, f"日期差异 {days_diff} 天在偏移范围内"
    else:
        return False, f"日期差异 {days_diff} 天超出偏移 ±{offset_days} 天"

def build_matching_key(item: dict, ignored_fields: List[str]) -> tuple:
    effective_ignored = set(ignored_fields)
    
    if 'supplier_code' in ignored_fields:
        effective_ignored.add('supplier_name')
    
    key_parts = []
    
    matching_fields = ['supplier_code', 'item_code', 'supplier_name']
    
    for field in matching_fields:
        if field not in effective_ignored:
            value = item.get(field, '')
            key_parts.append(str(value) if value else '')
    
    if not key_parts:
        key_parts = [item.get('item_code', '')]
    
    return tuple(key_parts)

def read_supplier_bill(file_path: str) -> List[SupplierBillItem]:
    items = []
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            items.append(SupplierBillItem(
                bill_no=row['bill_no'],
                item_code=row['item_code'],
                item_name=row['item_name'],
                quantity=float(row['quantity']),
                unit_price=float(row['unit_price']),
                amount=float(row['amount']),
                bill_date=row['bill_date'],
                supplier_code=row['supplier_code'],
                supplier_name=row['supplier_name']
            ))
    return items

def read_receiving_list(file_path: str) -> List[ReceivingListItem]:
    items = []
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            items.append(ReceivingListItem(
                receive_no=row['receive_no'],
                item_code=row['item_code'],
                item_name=row['item_name'],
                quantity=float(row['quantity']),
                unit_price=float(row['unit_price']),
                amount=float(row['amount']),
                receive_date=row['receive_date'],
                supplier_code=row['supplier_code'],
                supplier_name=row['supplier_name'],
                purchase_order_no=row['purchase_order_no']
            ))
    return items

def validate_supplier_bill_full(file_path: str) -> ValidationResult:
    result = ValidationResult()
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            
            missing_fields = [f for f in BILL_REQUIRED_FIELDS if f not in fieldnames]
            if missing_fields:
                result.errors.append(ValidationError(
                    row=0,
                    field="header",
                    value="",
                    error_type="MISSING_FIELD",
                    message=f"文件缺少必需字段: {', '.join(missing_fields)}"
                ))
                return result
            
            for row_idx, row in enumerate(reader, start=1):
                for field in BILL_REQUIRED_FIELDS:
                    if field not in row or row[field] is None or row[field].strip() == '':
                        result.errors.append(ValidationError(
                            row=row_idx,
                            field=field,
                            value="",
                            error_type="EMPTY_FIELD",
                            message=f"字段 {field} 不能为空"
                        ))
                    elif field in BILL_NUMERIC_FIELDS:
                        try:
                            float(row[field])
                        except ValueError:
                            result.errors.append(ValidationError(
                                row=row_idx,
                                field=field,
                                value=row[field],
                                error_type="INVALID_NUMBER",
                                message=f"字段 {field} 必须是数字，当前值: {row[field]}"
                            ))
                
                if not result.errors or not any(e.row == row_idx for e in result.errors):
                    result.valid_rows.append(dict(row))
    except Exception as e:
        result.errors.append(ValidationError(
            row=0,
            field="file",
            value="",
            error_type="FILE_ERROR",
            message=f"无法读取文件: {str(e)}"
        ))
    
    return result

def validate_receiving_list_full(file_path: str) -> ValidationResult:
    result = ValidationResult()
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            
            missing_fields = [f for f in RECEIVE_REQUIRED_FIELDS if f not in fieldnames]
            if missing_fields:
                result.errors.append(ValidationError(
                    row=0,
                    field="header",
                    value="",
                    error_type="MISSING_FIELD",
                    message=f"文件缺少必需字段: {', '.join(missing_fields)}"
                ))
                return result
            
            for row_idx, row in enumerate(reader, start=1):
                for field in RECEIVE_REQUIRED_FIELDS:
                    if field not in row or row[field] is None or row[field].strip() == '':
                        result.errors.append(ValidationError(
                            row=row_idx,
                            field=field,
                            value="",
                            error_type="EMPTY_FIELD",
                            message=f"字段 {field} 不能为空"
                        ))
                    elif field in RECEIVE_NUMERIC_FIELDS:
                        try:
                            float(row[field])
                        except ValueError:
                            result.errors.append(ValidationError(
                                row=row_idx,
                                field=field,
                                value=row[field],
                                error_type="INVALID_NUMBER",
                                message=f"字段 {field} 必须是数字，当前值: {row[field]}"
                            ))
                
                if not result.errors or not any(e.row == row_idx for e in result.errors):
                    result.valid_rows.append(dict(row))
    except Exception as e:
        result.errors.append(ValidationError(
            row=0,
            field="file",
            value="",
            error_type="FILE_ERROR",
            message=f"无法读取文件: {str(e)}"
        ))
    
    return result

def generate_batch_no() -> str:
    from datetime import datetime
    now = datetime.now()
    return f"BATCH_{now.strftime('%Y%m%d_%H%M%S')}"

def validate_csv_structure(file_path: str, required_fields: List[str]) -> Tuple[bool, List[str]]:
    errors = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            missing_fields = [f for f in required_fields if f not in fieldnames]
            if missing_fields:
                errors.append(f"文件缺少必需字段: {', '.join(missing_fields)}")
                return False, errors
            return True, []
    except Exception as e:
        errors.append(f"无法读取文件 {file_path}: {str(e)}")
        return False, errors

def validate_path_conflict(path: str) -> Tuple[bool, str]:
    if not path:
        return False, "路径不能为空"
    
    path_dir = path.rsplit('/', 1)[0] if '/' in path else path.rsplit('\\', 1)[0] if '\\' in path else '.'
    
    if not path_dir or path_dir == path:
        path_dir = '.'
    
    if not os.path.exists(path_dir):
        try:
            os.makedirs(path_dir, exist_ok=True)
        except Exception as e:
            return False, f"无法创建目录 {path_dir}: {str(e)}"
    
    if os.path.exists(path):
        if os.path.isdir(path):
            return False, f"目标路径是目录而非文件: {path}"
        return False, f"目标文件已存在: {path}"
    
    return True, ""

import os