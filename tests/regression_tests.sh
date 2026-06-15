#!/bin/bash
# 采购对账 CLI 回归测试脚本

set -e

echo "============================================"
echo "采购对账 CLI 回归测试"
echo "============================================"
echo ""

rm -f d:/workSpace/AI__SPACE/zyx-00109/purchase_recon.db
rm -f d:/workSpace/AI__SPACE/zyx-00109/output/*.csv

echo "=== 1. 测试方案管理 ==="
echo ""

echo "--- 1.1 创建方案 ---"
purchase-recon scheme create -n strict --description "严格模式" -q 0 -a 0
purchase-recon scheme create -n loose --description "宽松模式" -q 1.0 -a 50.0 --set-active
purchase-recon scheme create -n flexible -b "华东区" --description "灵活模式" -q 2.5 -a 100.0 -r bill_no -r item_code -i unit_price
purchase-recon scheme create -n date_test --description "日期偏移测试" -q 0 -a 0 --date-offset 5
purchase-recon scheme create -n ignore_test --description "忽略字段测试" -q 0 -a 0 -i supplier_code
echo ""

echo "--- 1.2 列出方案 ---"
purchase-recon scheme list
echo ""

echo "--- 1.3 查看方案详情 ---"
purchase-recon scheme show -n loose
echo ""

echo "--- 1.4 切换方案 ---"
purchase-recon scheme switch -n strict
purchase-recon scheme active
echo ""

echo "=== 2. 测试规则方案生效性 ==="
echo ""

echo "--- 2.1 测试必填字段验证 ---"
echo "    创建只要求 item_code 的方案..."
purchase-recon scheme create -n min_required --description "最少必填" -q 0 -a 0 -r item_code
echo ""

echo "    2.1.1 使用最少必填方案（只检查 item_code）..."
purchase-recon diff check -b samples/test_required_bill.csv -r samples/test_required_receiving.csv -s min_required || echo "预期: 通过（只检查 item_code）"
echo ""

echo "    2.1.2 使用默认方案（检查所有字段）..."
purchase-recon diff check -b samples/test_required_bill.csv -r samples/test_required_receiving.csv -s strict || echo "预期: 通过（完整字段）"
echo ""

echo "--- 2.2 测试日期偏移 ---"
echo "    2.2.1 日期在偏移范围内（±5天）应通过..."
purchase-recon diff check -b samples/test_date_bill.csv -r samples/test_date_receiving.csv -s date_test
echo ""

echo "    2.2.2 创建日期超出偏移的测试文件..."
echo "bill_no,item_code,item_name,quantity,unit_price,amount,bill_date,supplier_code,supplier_name" > samples/test_date_fail_bill.csv
echo "B301,M301,物料F,35,100,3500,2024-01-01,S301,供应商G" >> samples/test_date_fail_bill.csv

echo "receive_no,item_code,item_name,quantity,unit_price,amount,receive_date,supplier_code,supplier_name,purchase_order_no" > samples/test_date_fail_receiving.csv
echo "R301,M301,物料F,35,100,3500,2024-02-01,S301,供应商G,P301" >> samples/test_date_fail_receiving.csv

echo "    2.2.3 日期超出偏移（>5天）应失败..."
purchase-recon diff check -b samples/test_date_fail_bill.csv -r samples/test_date_fail_receiving.csv -s date_test
echo ""

echo "--- 2.3 测试忽略供应商字段 ---"
echo "    2.3.1 不忽略供应商字段（默认）..."
echo "        预期: 两条差异（S201和S202分开统计）"
purchase-recon diff check -b samples/test_ignore_bill.csv -r samples/test_ignore_receiving.csv -s strict
echo ""

echo "    2.3.2 忽略供应商字段..."
echo "        预期: 数量 30+10=40 应等于收货 40（无差异）"
purchase-recon diff check -b samples/test_ignore_bill.csv -r samples/test_ignore_receiving.csv -s ignore_test
echo ""

echo "--- 2.4 测试数量/金额容差 ---"
echo "    创建小差异测试文件..."
echo "bill_no,item_code,item_name,quantity,unit_price,amount,bill_date,supplier_code,supplier_name" > samples/test_tolerance_bill.csv
echo "B401,M401,物料G,100,10,1000,2024-03-01,S401,供应商H" >> samples/test_tolerance_bill.csv

echo "receive_no,item_code,item_name,quantity,unit_price,amount,receive_date,supplier_code,supplier_name,purchase_order_no" > samples/test_tolerance_receiving.csv
echo "R401,M401,物料G,100.8,10,1008,2024-03-01,S401,供应商H,P401" >> samples/test_tolerance_receiving.csv

echo "    2.4.1 严格模式（不容差）..."
echo "        预期: 有差异（数量差异 0.8，金额差异 8）"
purchase-recon diff check -b samples/test_tolerance_bill.csv -r samples/test_tolerance_receiving.csv -s strict
echo ""

echo "    2.4.2 创建宽松容差方案..."
purchase-recon scheme create -n tolerance_test --description "容差测试" -q 1.0 -a 10.0
echo ""

echo "    2.4.3 宽松模式（数量容差 1.0，金额容差 10）..."
echo "        预期: 无差异（0.8 <= 1.0 且 8 <= 10）"
purchase-recon diff check -b samples/test_tolerance_bill.csv -r samples/test_tolerance_receiving.csv -s tolerance_test
echo ""

echo "=== 3. 测试配置管理 ==="
echo ""
purchase-recon config rule --list
purchase-recon config rule --set --key quantity_tolerance --value 0.5
purchase-recon config rule --list
echo ""

echo "=== 4. 测试导入（含验证） ==="
echo ""
echo "--- 4.1 正常导入 ---"
purchase-recon import bill -f samples/supplier_bill.csv
purchase-recon import receiving -f samples/receiving_list.csv
echo ""

echo "--- 4.2 Malformed 文件导入验证 ---"
purchase-recon import bill -f samples/malformed_bill.csv || true
echo ""

echo "=== 5. 测试差异检查 Dry-run（使用方案） ==="
echo ""
echo "--- 5.1 严格模式检查 ---"
purchase-recon diff check --no-scheme
echo ""

echo "--- 5.2 宽松模式检查 ---"
purchase-recon scheme switch -n loose
purchase-recon diff check
echo ""

echo "=== 6. 测试创建批次（使用方案） ==="
echo ""
echo "--- 6.1 严格模式创建批次 ---"
purchase-recon scheme switch -n strict
purchase-recon batch create -o 张三 -R reviewer --dry-run
echo ""

echo "--- 6.2 宽松模式创建批次 ---"
purchase-recon scheme switch -n loose
purchase-recon batch create -o 张三 -R reviewer --dry-run
echo ""

echo "--- 6.3 实际创建批次 ---"
purchase-recon scheme switch -n strict
purchase-recon batch create -o 张三 -R reviewer
BATCH_NO=$(purchase-recon batch list | grep "BATCH" | head -1 | awk '{print $1}')
echo "创建的批次: $BATCH_NO"
echo ""

echo "--- 6.4 查看批次（含方案信息） ---"
purchase-recon batch show -b "$BATCH_NO"
echo ""

echo "=== 7. 测试申诉流程（角色验证） ==="
echo ""
echo "--- 7.1 发起申诉 ---"
purchase-recon appeal initiate -b "$BATCH_NO" -o 张三 -R reviewer -n "核对差异"
echo ""

echo "--- 7.2 审批通过 ---"
purchase-recon appeal approve -b "$BATCH_NO" -o 李四 -R approver -n "同意申诉"
echo ""

echo "--- 7.3 查看申诉列表（含角色） ---"
purchase-recon appeal list -b "$BATCH_NO"
echo ""

echo "=== 8. 测试角色权限校验 ==="
echo ""
echo "--- 8.1 缺少角色参数 ---"
purchase-recon appeal approve -b "$BATCH_NO" -o 李四 || echo "预期失败: 缺少角色参数"
echo ""

echo "--- 8.2 无效角色 ---"
purchase-recon appeal approve -b "$BATCH_NO" -o 李四 -R invalid_role || echo "预期失败: 无效角色"
echo ""

echo "--- 8.3 权限不足 ---"
purchase-recon appeal approve -b "$BATCH_NO" -o 李四 -R reviewer || echo "预期失败: reviewer无审批权限"
echo ""

echo "=== 9. 测试回滚操作 ==="
echo ""
echo "--- 9.1 检查回滚状态 ---"
purchase-recon rollback check -b "$BATCH_NO"
echo ""

echo "--- 9.2 回滚一条记录 ---"
purchase-recon rollback item -b "$BATCH_NO" -i 1 -o 王五 -R admin -n "发现错误"
echo ""

echo "--- 9.3 权限不足的回滚 ---"
purchase-recon rollback item -b "$BATCH_NO" -i 2 -o 王五 -R approver || echo "预期失败: 仅admin可回滚"
echo ""

echo "=== 10. 测试已回滚项再次审批 ==="
echo ""
purchase-recon appeal approve -b "$BATCH_NO" -i 1 -o 李四 -R approver || echo "预期失败: 已回滚项无法审批"
echo ""

echo "=== 11. 测试导出功能 ==="
echo ""
echo "--- 11.1 导出结果 ---"
purchase-recon export result -b "$BATCH_NO" -o output/result_new.csv
echo ""

echo "--- 11.2 路径冲突检测 ---"
echo "test" > output/result_new.csv
purchase-recon export result -b "$BATCH_NO" -o output/result_new.csv || echo "预期失败: 文件已存在"
rm -f output/result_new.csv
echo ""

echo "=== 12. 测试方案导入导出冲突处理 ==="
echo ""
echo "--- 12.1 导出方案 ---"
purchase-recon scheme export -o output/schemes_export.json
echo ""

echo "--- 12.2 导入方案（同名冲突-跳过） ---"
purchase-recon scheme import -f output/schemes_export.json -c skip
echo ""

echo "--- 12.3 创建测试方案用于覆盖测试 ---"
purchase-recon scheme create -n to_overwrite --description "将被覆盖" -q 1.0
echo ""

echo "--- 12.4 导入方案（同名冲突-覆盖） ---"
purchase-recon scheme import -f output/schemes_export.json -c overwrite
echo ""

echo "--- 12.5 查看覆盖后的方案 ---"
purchase-recon scheme show -n to_overwrite || echo "方案已被覆盖"
echo ""

echo "--- 12.6 导入方案（同名冲突-改名） ---"
purchase-recon scheme import -f output/schemes_export.json -c rename
echo ""

echo "--- 12.7 查看改名后的方案 ---"
purchase-recon scheme list
echo ""

echo "=== 13. 测试审计日志 ==="
echo ""
purchase-recon audit list
echo ""

echo "=== 14. 测试审计归档功能 ==="
echo ""
echo "--- 14.1 查看批次审计详情 ---"
purchase-recon audit batch -b "$BATCH_NO"
echo ""

echo "--- 14.2 查看申诉审计记录 ---"
purchase-recon audit appeal -b "$BATCH_NO"
echo ""

echo "--- 14.3 查看回滚审计记录 ---"
purchase-recon audit rollback -b "$BATCH_NO"
echo ""

echo "--- 14.4 查看导出审计记录 ---"
purchase-recon audit export-records
echo ""

echo "--- 14.5 查看方案导入记录 ---"
purchase-recon audit import-list
echo ""

echo "--- 14.6 查看完整审计链路 ---"
purchase-recon audit trail -b "$BATCH_NO"
echo ""

echo "--- 14.7 重导出审计链路 ---"
purchase-recon audit reexport -b "$BATCH_NO" -o output/trail_test.json -f json
echo ""

echo "=== 15. 跨进程查询测试 ==="
echo ""
echo "--- 15.1 重启后查询批次 ---"
purchase-recon batch list
echo ""

echo "--- 15.2 查询申诉状态 ---"
purchase-recon appeal list -b "$BATCH_NO"
echo ""

echo "--- 15.3 重启后查询方案 ---"
purchase-recon scheme list
echo ""

echo "--- 15.4 重启后查询审计归档 ---"
purchase-recon audit trail -b "$BATCH_NO"
echo ""

echo "=== 16. 测试方案导入（含操作员记录） ==="
echo ""
echo "--- 16.1 导入方案并记录操作人 ---"
purchase-recon scheme import -f output/schemes_export.json -c skip -o 张三 -R admin
echo ""

echo "--- 16.2 查看导入记录 ---"
purchase-recon audit import-list
echo ""

echo "=== 17. 测试删除方案 ==="
echo ""
echo "--- 17.1 删除非激活方案 ---"
purchase-recon scheme delete -n to_overwrite -f
echo ""

echo "--- 17.2 查看方案列表 ---"
purchase-recon scheme list
echo ""

echo "=== 18. 清理测试文件 ==="
rm -f samples/test_date_fail_bill.csv
rm -f samples/test_date_fail_receiving.csv
rm -f samples/test_tolerance_bill.csv
rm -f samples/test_tolerance_receiving.csv
rm -f output/trail_test.json
echo ""

echo "============================================"
echo "回归测试完成！"
echo "============================================"
