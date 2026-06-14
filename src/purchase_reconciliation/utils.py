import csv
from typing import List, Tuple, Optional
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