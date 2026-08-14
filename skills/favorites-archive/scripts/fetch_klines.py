#!/usr/bin/env python3
"""批量拉取 A 股日线（腾讯行情 API，免费免 key），用于博主预测对照 / 回测验证。

用法:
  python3 fetch_klines.py sh000001 sz300308 sh600183 2026-07-24 2026-08-08
输出: 每标的 日期/开/收/高/低/涨跌幅，末尾区间涨跌（对照预测起点→终点）。

代码格式: sh000001(上证) sz399006(创业板) sz300308(中际旭创) sh600183(生益科技)...
备选源: 东财 push2his 偶发限流(HTTP 000)；新浪 quotes.sina.cn 作第三备选。
"""
import json
import subprocess
import sys
import time


def fetch(code, beg, end):
    url = (f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
           f"?param={code},day,{beg},{end},200,qfq")
    r = subprocess.run(["curl", "-s", "--max-time", "20", url],
                       capture_output=True, text=True, timeout=30)
    d = json.loads(r.stdout)
    data = d.get("data", {}).get(code, {})
    return data.get("qfqday") or data.get("day") or []


def main():
    if len(sys.argv) >= 4:
        codes, beg, end = sys.argv[1:-2], sys.argv[-2], sys.argv[-1]
    else:
        print("用法: fetch_klines.py <code...> <beg> <end>  "
              "e.g. sh000001 sz300308 2026-07-24 2026-08-08")
        return
    for code in codes:
        try:
            kl = fetch(code, beg, end)
            if not kl:
                print(f"### {code}: 无数据")
                continue
            print(f"### {code}  ({kl[0][0]} ~ {kl[-1][0]})")
            prev = None
            for k in kl:
                date, o, c, h, l = k[0], float(k[1]), float(k[2]), k[3], k[4]
                chg = f"{(c/prev-1)*100:+.2f}%" if prev else ""
                print(f"  {date}  开{o:>10.2f}  收{c:>10.2f}  "
                      f"高{h:>10}  低{l:>10}  {chg}")
                prev = c
            first, last = float(kl[0][2]), float(kl[-1][2])
            print(f"  >>> 区间 {(last/first-1)*100:+.1f}%  ({first} → {last})\n")
        except Exception as e:
            print(f"### {code}: ERROR {e}")
        time.sleep(0.5)


if __name__ == "__main__":
    main()
