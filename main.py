import tkinter as tk
from ttkbootstrap import Style, Progressbar, Treeview
import dns.resolver
import threading
import time
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Lock


class DNSTester:
    def __init__(self):
        self.window = tk.Tk()
        self.style = Style(theme='flatly')
        self.servers = []  # DNS服务器列表
        self.domains = []  # 待测试域名列表
        self.test_domain = tk.StringVar()  # 用户输入的单个域名
        self.test_mode = tk.IntVar()  # 测试模式（0: 单域名，1: 多域名）
        self.completed_tests = 0  # 已完成的测试数量
        self.total_tests = 0  # 总测试数量
        self.server_results = {}  # 每个DNS服务器的测试结果
        self.server_lock = Lock()  # 线程锁，用于线程安全
        self.all_dns_results = []  # 保存所有 DNS 测试结果
        self.progress_value = 0  # 进度条当前值

        # 初始化GUI
        self.create_widgets()
        self.load_dns_list()
        self.load_domains_from_file()
        self.show_initial_tables()
        self.configure_tags()  # 配置颜色标签

    def create_widgets(self):
        # 主窗口
        self.window.title("DNS 服务器测试工具")
        main_container = tk.Frame(self.window)
        main_container.pack(fill='both', expand=True)

        # 左侧：DNS服务器表格
        left_frame = tk.Frame(main_container, borderwidth=1, relief='solid')
        left_frame.pack(side='left', fill='both', expand=True, padx=5, pady=5)

        dns_table_frame = tk.Frame(left_frame)
        dns_table_frame.pack(fill='both', expand=True, pady=10)

        self.scrollbar = tk.Scrollbar(dns_table_frame, orient="vertical")
        self.scrollbar.pack(side="right", fill="y")

        self.treeview = Treeview(
            dns_table_frame,
            columns=('server', 'latency'),
            show='headings',
            style='Treeview',
            height=15,
            yscrollcommand=self.scrollbar.set
        )
        self.treeview.pack(side="left", fill="both", expand=True)
        self.scrollbar.config(command=self.treeview.yview)

        self.treeview.heading('server', text='DNS 服务器')
        self.treeview.heading('latency', text='响应时间 (ms)')
        self.treeview.column('latency', anchor='e')

        # 右侧：域名输入和表格
        right_frame = tk.Frame(main_container)
        right_frame.pack(side='left', fill='both', expand=True, padx=5, pady=5)

        input_frame = tk.Frame(right_frame)
        input_frame.pack(pady=10, padx=10, anchor='w', fill='x')

        input_label = tk.Label(input_frame, text="请输入待测网址：")
        input_label.pack(side='left')

        self.domain_entry = tk.Entry(input_frame, textvariable=self.test_domain, width=20)
        self.domain_entry.pack(side='left', padx=10)
        self.test_domain.set("example.com")

        mode_frame = tk.Frame(input_frame)
        mode_frame.pack(side='left', padx=10)

        single_mode_label = tk.Label(mode_frame, text="测试模式：")
        single_mode_label.pack(side='top', anchor='w')

        self.single_mode_radio = tk.Radiobutton(
            mode_frame,
            text="单域名测试",
            variable=self.test_mode,
            value=0
        )
        self.single_mode_radio.pack(anchor='w')

        self.multi_mode_radio = tk.Radiobutton(
            mode_frame,
            text="多域名测试",
            variable=self.test_mode,
            value=1
        )
        self.multi_mode_radio.pack(anchor='w')

        self.test_btn = tk.Button(
            input_frame,
            text="开始测试",
            command=self.start_test_thread,
            width=10
        )
        self.test_btn.pack(side='left', pady=10)

        domain_table_frame = tk.Frame(right_frame)
        domain_table_frame.pack(fill='both', expand=True, pady=10)

        self.domain_treeview = Treeview(
            domain_table_frame,
            columns=('domain', 'latency'),
            show='headings',
            style='Treeview',
            height=15,
        )
        self.domain_treeview.pack(side="left", fill="both", expand=True, padx=5)
        self.domain_treeview.heading('domain', text='域名')
        self.domain_treeview.heading('latency', text='响应时间 (ms)')
        self.domain_treeview.column('latency', anchor='e')

        # 进度条和进度标签
        self.progress_container = tk.Frame(self.window)
        self.progress_container.pack(side="bottom", fill="x", pady=10)

        self.progress = Progressbar(
            self.progress_container,
            length=300,
            mode='determinate'
        )
        self.progress.pack(side="left", fill="x", expand=True, padx=10)

        self.progress_label = tk.Label(
            self.progress_container,
            text="进度: 0%",
            anchor="e",
            width=20
        )
        self.progress_label.pack(side="left", padx=10)

    def load_dns_list(self):
        """从文件加载DNS服务器列表"""
        if not os.path.exists('dns_servers.txt'):
            print("未找到 dns_servers.txt 文件")
            return

        with open('dns_servers.txt', 'r', encoding='utf-8') as f:
            self.servers = [line.strip() for line in f if line.strip() and not line.startswith('#')]

        print(f"加载了 {len(self.servers)} 个 DNS 服务器")

    def load_domains_from_file(self):
        """从文件加载待测试域名列表"""
        if not os.path.exists('domains.txt'):
            print("未找到 domains.txt 文件，使用默认域名 example.com")
            self.domains = ["example.com"]
            return

        with open('domains.txt', 'r', encoding='utf-8') as f:
            self.domains = [line.strip() for line in f if line.strip() and not line.startswith('#')]

        print(f"加载了 {len(self.domains)} 个待测试域名")

    def show_initial_tables(self):
        """在表格中显示初始DNS服务器和域名列表"""
        for server in self.servers:
            self.treeview.insert('', 'end', values=(server, "未测试"))

        for domain in self.domains:
            self.domain_treeview.insert('', 'end', values=(domain, "未测试"))

    def configure_tags(self):
        """配置颜色标签"""
        self.treeview.tag_configure('green', foreground='#008000')  # 绿色
        self.treeview.tag_configure('yellow', foreground='#FFD700')  # 金黄色
        self.treeview.tag_configure('orange', foreground='#FFA500')  # 橙色
        self.treeview.tag_configure('red', foreground='#FF0000')  # 红色
        self.treeview.tag_configure('test', foreground='#808080')  # 灰色（用于“测试中”）
        self.domain_treeview.tag_configure('untested', foreground='#808080')  # 灰色（用于“未测试”）

    def start_test_thread(self):
        """启动测试线程"""
        self.test_btn.config(state='disabled')
        self.domain_entry.config(state='disabled')
        self.show_testing_status()  # 显示“测试中”状态
        threading.Thread(target=self.run_tests).start()

    def show_testing_status(self):
        """显示“测试中”状态"""
        for item in self.treeview.get_children():
            self.treeview.set(item, 'latency', "测试中")
            self.treeview.item(item, tags=('test',))  # 设置灰色字体

        for item in self.domain_treeview.get_children():
            self.domain_treeview.set(item, 'latency', "测试中")
            self.domain_treeview.item(item, tags=('test',))  # 设置灰色字体

    def test_single_dns(self, server, domain):
        """测试单个DNS服务器对单个域名的响应时间"""
        resolver = dns.resolver.Resolver()
        resolver.nameservers = [server]
        resolver.lifetime = 2
        resolver.timeout = 2

        start = time.time()
        try:
            answers = resolver.resolve(domain, 'A')
            elapsed = (time.time() - start) * 1000  # 转换为毫秒
            result = f"{elapsed:.2f} ms"
        except dns.resolver.NXDOMAIN:
            result = "NXDOMAIN"
        except dns.resolver.NoNameservers:
            result = "NoNameservers"
        except dns.resolver.Timeout:
            result = "超时"
        except Exception as e:
            result = f"错误: {e}"

        # 更新结果
        with self.server_lock:
            if server not in self.server_results:
                self.server_results[server] = {"total_latency": 0, "count": 0, "results": []}
            if result.endswith("ms"):
                self.server_results[server]["total_latency"] += float(result[:-3])
                self.server_results[server]["count"] += 1
            self.server_results[server]["results"].append(result)

        # 更新域名测试结果
        self.all_dns_results.append((domain, result))

        # 更新进度
        self.completed_tests += 1
        self.update_progress()

    def run_tests(self):
        """运行DNS服务器测试"""
        self.completed_tests = 0
        self.server_results.clear()
        self.all_dns_results.clear()

        if self.test_mode.get() == 0:
            domains = [self.test_domain.get()]
        else:
            domains = self.domains

        self.total_tests = len(self.servers) * len(domains)

        with ThreadPoolExecutor(max_workers=20) as executor:
            for server in self.servers:
                for domain in domains:
                    executor.submit(self.test_single_dns, server, domain)

        # 更新表格
        self.update_dns_table()
        self.update_domain_table()
        self.test_btn.config(state='normal')
        self.domain_entry.config(state='normal')

    def update_progress(self):
        """更新进度条和进度标签"""
        self.progress_value = (self.completed_tests / self.total_tests) * 100
        self.progress['value'] = self.progress_value
        self.progress_label.config(text=f"进度: {self.completed_tests}/{self.total_tests} ({self.progress_value:.2f}%)")
        self.window.update_idletasks()

    def update_dns_table(self):
        """更新DNS服务器表格"""
        # 清空表格
        for row in self.treeview.get_children():
            self.treeview.delete(row)

        # 按响应时间排序
        sorted_servers = sorted(
            self.servers,
            key=lambda s: (
                (self.server_results.get(s, {}).get("total_latency", float('inf')) /
                 max(self.server_results.get(s, {}).get("count", 0), 1))
            ) if self.server_results.get(s, {}).get("count", 0) > 0 else float('inf')
        )

        # 重新插入数据
        for server in sorted_servers:
            result = self.server_results.get(server, {})
            count = result.get("count", 0)
            total_latency = result.get("total_latency", 0)
            avg_latency = total_latency / count if count > 0 else float('inf')

            if avg_latency == float('inf'):
                latency_str = "超时"
                tag = 'red'
            else:
                latency_str = f"{avg_latency:.2f} ms"
                tag = 'green' if avg_latency < 50 else 'yellow' if avg_latency < 200 else 'orange' if avg_latency < 500 else 'red'

            self.treeview.insert('', 'end', values=(server, latency_str), tags=(tag,))

    def update_domain_table(self):
        """更新域名表格，计算每个域名的平均响应时间（排除超时）"""
        # 清空表格
        for row in self.domain_treeview.get_children():
            self.domain_treeview.delete(row)

        # 重新插入数据
        domain_latencies = {}
        for domain, result in self.all_dns_results:
            if domain not in domain_latencies:
                domain_latencies[domain] = []
            if result.endswith("ms"):
                domain_latencies[domain].append(float(result[:-3]))

        # 根据测试模式选择域名
        if self.test_mode.get() == 0:
            domains_to_update = [self.test_domain.get()]
        else:
            domains_to_update = self.domains

        # 更新表格
        for domain in self.domains:
            tag = ''
            if domain in domains_to_update:
                latencies = domain_latencies.get(domain, [])
                if latencies:
                    avg_latency = sum(latencies) / len(latencies)
                    latency_str = f"{avg_latency:.2f} ms"
                    # 设置颜色标签
                    if avg_latency < 50:
                        tag = 'green'
                    elif avg_latency < 200:
                        tag = 'yellow'
                    elif avg_latency < 500:
                        tag = 'orange'
                    else:
                        tag = 'red'
                else:
                    latency_str = "超时"
                    tag = 'red'
            else:
                latency_str = "未测试"
                tag = 'untested'  # 设置未测试的标签

            self.domain_treeview.insert('', 'end', values=(domain, latency_str), tags=(tag,))

    def run(self):
        """运行主循环"""
        self.window.mainloop()


if __name__ == '__main__':
    app = DNSTester()
    app.run()