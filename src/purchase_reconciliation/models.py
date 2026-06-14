from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, List

class DocumentType(Enum):
    SUPPLIER_BILL = "supplier_bill"
    RECEIVING_LIST = "receiving_list"

class AppealStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ROLLED_BACK = "rolled_back"

class BatchStatus(Enum):
    OPEN = "open"
    LOCKED = "locked"
    COMPLETED = "completed"

@dataclass
class SupplierBillItem:
    bill_no: str
    item_code: str
    item_name: str
    quantity: float
    unit_price: float
    amount: float
    bill_date: str
    supplier_code: str
    supplier_name: str

@dataclass
class ReceivingListItem:
    receive_no: str
    item_code: str
    item_name: str
    quantity: float
    unit_price: float
    amount: float
    receive_date: str
    supplier_code: str
    supplier_name: str
    purchase_order_no: str

@dataclass
class DiffItem:
    bill_no: str
    receive_no: str
    item_code: str
    item_name: str
    bill_quantity: float
    receive_quantity: float
    quantity_diff: float
    bill_amount: float
    receive_amount: float
    amount_diff: float
    supplier_code: str
    supplier_name: str
    id: Optional[int] = None
    batch_id: Optional[int] = None
    status: AppealStatus = AppealStatus.PENDING
    appeal_note: str = ""
    operator: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@dataclass
class Batch:
    batch_no: str
    id: Optional[int] = None
    status: BatchStatus = BatchStatus.OPEN
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    locked_by: Optional[str] = None
    lock_time: Optional[datetime] = None

@dataclass
class AuditLog:
    batch_id: int
    batch_no: str
    operation: str
    operator: str
    id: Optional[int] = None
    target_item_id: Optional[int] = None
    note: str = ""
    created_at: Optional[datetime] = None

@dataclass
class Config:
    key: str
    value: str
    id: Optional[int] = None
    description: str = ""
    updated_at: Optional[datetime] = None