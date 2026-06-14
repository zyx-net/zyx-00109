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

echo "--- 1.5 导出方案 ---"
purchase-recon scheme export -o output/schemes_export.json
cat output/schemes_export.json
echo ""

echo "--- 1.6 更新方案 ---"
purchase-recon scheme update -n strict -q 0.5 -a 25.0
purchase-recon scheme show -n strict
echo ""

echo "=== 2. 测试配置管理 ==="
echo ""
purchase-recon config rule --list
purchase-recon config rule --set --key quantity_tolerance --value 0.5
purchase-recon config rule --list
echo ""

echo "=== 3. 测试导入（含验证） ==="
echo ""
echo "--- 3.1 正常导入 ---"
purchase-recon import bill -f samples/supplier_bill.csv
purchase-recon import receiving -f samples/receiving_list.csv
echo ""

echo "--- 3.2 Malformed 文件导入验证 ---"
purchase-recon import bill -f samples/malformed_bill.csv || true
echo ""

echo "=== 4. 测试差异检查 Dry-run（使用方案） ==="
echo ""
echo "--- 4.1 严格模式检查 ---"
purchase-recon diff check --no-scheme
echo ""

echo "--- 4.2 宽松模式检查 ---"
purchase-recon scheme switch -n loose
purchase-recon diff check
echo ""

echo "=== 5. 测试创建批次（使用方案） ==="
echo ""
echo "--- 5.1 严格模式创建批次 ---"
purchase-recon scheme switch -n strict
purchase-recon batch create -o 张三 -R reviewer --dry-run
echo ""

echo "--- 5.2 宽松模式创建批次 ---"
purchase-recon scheme switch -n loose
purchase-recon batch create -o 张三 -R reviewer --dry-run
echo ""

echo "--- 5.3 实际创建批次 ---"
purchase-recon scheme switch -n strict
purchase-recon batch create -o 张三 -R reviewer
BATCH_NO=$(purchase-recon batch list | grep "BATCH" | head -1 | awk '{print $1}')
echo "创建的批次: $BATCH_NO"
echo ""

echo "--- 5.4 查看批次（含方案信息） ---"
purchase-recon batch show -b "$BATCH_NO"
echo ""

echo "=== 6. 测试申诉流程（角色验证） ==="
echo ""
echo "--- 6.1 发起申诉 ---"
purchase-recon appeal initiate -b "$BATCH_NO" -o 张三 -R reviewer -n "核对差异"
echo ""

echo "--- 6.2 审批通过 ---"
purchase-recon appeal approve -b "$BATCH_NO" -o 李四 -R approver -n "同意申诉"
echo ""

echo "--- 6.3 查看申诉列表（含角色） ---"
purchase-recon appeal list -b "$BATCH_NO"
echo ""

echo "=== 7. 测试角色权限校验 ==="
echo ""
echo "--- 7.1 缺少角色参数 ---"
purchase-recon appeal approve -b "$BATCH_NO" -o 李四 || echo "预期失败: 缺少角色参数"
echo ""

echo "--- 7.2 无效角色 ---"
purchase-recon appeal approve -b "$BATCH_NO" -o 李四 -R invalid_role || echo "预期失败: 无效角色"
echo ""

echo "--- 7.3 权限不足 ---"
purchase-recon appeal approve -b "$BATCH_NO" -o 李四 -R reviewer || echo "预期失败: reviewer无审批权限"
echo ""

echo "=== 8. 测试回滚操作 ==="
echo ""
echo "--- 8.1 检查回滚状态 ---"
purchase-recon rollback check -b "$BATCH_NO"
echo ""

echo "--- 8.2 回滚一条记录 ---"
purchase-recon rollback item -b "$BATCH_NO" -i 1 -o 王五 -R admin -n "发现错误"
echo ""

echo "--- 8.3 权限不足的回滚 ---"
purchase-recon rollback item -b "$BATCH_NO" -i 2 -o 王五 -R approver || echo "预期失败: 仅admin可回滚"
echo ""

echo "=== 9. 测试已回滚项再次审批 ==="
echo ""
purchase-recon appeal approve -b "$BATCH_NO" -i 1 -o 李四 -R approver || echo "预期失败: 已回滚项无法审批"
echo ""

echo "=== 10. 测试导出功能 ==="
echo ""
echo "--- 10.1 导出结果 ---"
purchase-recon export result -b "$BATCH_NO" -o output/result_new.csv
echo ""

echo "--- 10.2 路径冲突检测 ---"
echo "test" > output/result_new.csv
purchase-recon export result -b "$BATCH_NO" -o output/result_new.csv || echo "预期失败: 文件已存在"
rm -f output/result_new.csv
echo ""

echo "=== 11. 测试方案导入导出冲突处理 ==="
echo ""
echo "--- 11.1 导入方案（同名冲突-跳过） ---"
purchase-recon scheme import -f output/schemes_export.json -c skip
echo ""

echo "--- 11.2 创建测试方案用于覆盖测试 ---"
purchase-recon scheme create -n to_overwrite --description "将被覆盖" -q 1.0
echo ""

echo "--- 11.3 导入方案（同名冲突-覆盖） ---"
purchase-recon scheme import -f output/schemes_export.json -c overwrite
echo ""

echo "--- 11.4 查看覆盖后的方案 ---"
purchase-recon scheme show -n to_overwrite || echo "方案已被覆盖"
echo ""

echo "--- 11.5 导入方案（同名冲突-改名） ---"
purchase-recon scheme import -f output/schemes_export.json -c rename
echo ""

echo "--- 11.6 查看改名后的方案 ---"
purchase-recon scheme list
echo ""

echo "=== 12. 测试审计日志 ==="
echo ""
purchase-recon audit list
echo ""

echo "=== 13. 跨进程查询测试 ==="
echo ""
echo "--- 13.1 重启后查询批次 ---"
purchase-recon batch list
echo ""

echo "--- 13.2 查询申诉状态 ---"
purchase-recon appeal list -b "$BATCH_NO"
echo ""

echo "--- 13.3 重启后查询方案 ---"
purchase-recon scheme list
echo ""

echo "=== 14. 测试删除方案 ==="
echo ""
echo "--- 14.1 删除非激活方案 ---"
purchase-recon scheme delete -n to_overwrite -f
echo ""

echo "--- 14.2 查看方案列表 ---"
purchase-recon scheme list
echo ""

echo "============================================"
echo "回归测试完成！"
echo "============================================"
