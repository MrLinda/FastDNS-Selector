import tkinter as tk
from ttkbootstrap import Style, Progressbar, Treeview
import dns.resolver
import threading
import time
import os
from concurrent.futures import ThreadPoolExecutor


class DNSTester:
    def __init__(self):
        self.window = tk.Tk()
        self.style = Style(theme='flatly')
        self.results = []
        self.servers = []
        self.domains = []
        self.completed_tests = 0  # 用于跟踪已完成的测试数量
        self.test_domain = tk.StringVar()  # 用于存储用户输入的域名
        self.test_mode = tk.IntVar()  # 用于存储用户选择的测试模式（0：单域名，1：多域名）
        self.all_dns_results = []  # 存储所有DNS服务器的解析结果

        # 设置窗口标题
        self.window.title("DNS 服务器测试工具")  # 添加窗口标题

        # GUI组件初始化
        self.create_widgets()
        self.load_dns_list()
        self.load_domains_from_file()  # 从文件加载域名
        self.show_initial_tables()  # 显示初始表格

        # 配置颜色标签
        self.configure_tags()

    def create_widgets(self):
        # 水平排布的容器
        main_container = tk.Frame(self.window)
        main_container.pack(fill='both', expand=True)

        # 左侧容器：DNS 服务器表格
        left_frame = tk.Frame(main_container, borderwidth=1, relief='solid')
        left_frame.pack(side='left', fill='both', expand=True, padx=5, pady=5)

        # 左侧 DNS 表格
        dns_table_frame = tk.Frame(left_frame)
        dns_table_frame.pack(fill='both', expand=True, pady=10)

        # DNS 表格滚动条
        self.scrollbar = tk.Scrollbar(dns_table_frame, orient="vertical")
        self.scrollbar.pack(side="right", fill="y")

        # DNS 表格
        self.treeview = Treeview(
            dns_table_frame,
            columns=('server', 'latency'),
            show='headings',
            style='Treeview',
            height=15,
            yscrollcommand=self.scrollbar.set
        )
        self.treeview.pack(side="left", fill="both", expand=True)

        # 配置滚动条
        self.scrollbar.config(command=self.treeview.yview)

        # 设置 DNS 表格表头
        self.treeview.heading('server', text='DNS 服务器')
        self.treeview.heading('latency', text='响应时间 (ms)')
        self.treeview.column('latency', anchor='e')

        # 右侧容器：域名表格和输入框
        right_frame = tk.Frame(main_container)
        right_frame.pack(side='left', fill='both', expand=True, padx=5, pady=5)

        # 右侧顶部：输入框、单选框和按钮
        input_frame = tk.Frame(right_frame)
        input_frame.pack(pady=10, padx=10, anchor='w', fill='x')  # 使用 anchor='w' 靠左对齐

        # 输入框
        input_label = tk.Label(input_frame, text="请输入待测网址：")
        input_label.pack(side='left')

        self.domain_entry = tk.Entry(input_frame, textvariable=self.test_domain, width=20)
        self.domain_entry.pack(side='left', padx=10)
        self.test_domain.set("example.com")  # 设置默认值

        # 单选框：选择测试模式
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

        # 测试按钮
        self.test_btn = tk.Button(
            input_frame,
            text="开始测试",
            command=self.start_test_thread,
            width=10
        )
        self.test_btn.pack(side='left', pady=10)

        # 右侧底部：域名表格
        domain_table_frame = tk.Frame(right_frame)
        domain_table_frame.pack(fill='both', expand=True, pady=10)

        # 域名表格
        self.domain_treeview = Treeview(
            domain_table_frame,
            columns=('domain', 'latency'),
            show='headings',
            style='Treeview',
            height=15,
        )
        self.domain_treeview.pack(side="left", fill="both", expand=True, padx=5)

        # 设置域名表格表头
        self.domain_treeview.heading('domain', text='域名')
        self.domain_treeview.heading('latency', text='响应时间 (ms)')
        self.domain_treeview.column('latency', anchor='e')

        # 进度条和进度标签的容器
        self.progress_container = tk.Frame(self.window)
        self.progress_container.pack(side="bottom", fill="x", pady=10)  # 填充整个底部

        # 进度条
        self.progress = Progressbar(
            self.progress_container,
            length=300,  # 移除长度限制，让进度条动态填充
            mode='determinate'
        )
        self.progress.pack(side="left", fill="x", expand=True, padx=10)  # 让进度条动态扩展

        # 进度显示标签
        self.progress_label = tk.Label(
            self.progress_container,
            text="进度: 0%",
            anchor="e",  # 标签内容靠右对齐
            width=20  # 固定宽度确保标签不会占据太多空间
        )
        self.progress_label.pack(side="left", padx=10)

    def load_dns_list(self):
        """从 dns_servers.txt 加载 DNS 服务器列表，忽略以 # 开头的注释行"""
        if not os.path.exists('dns_servers.txt'):
            print("未找到 dns_servers.txt 文件")
            return

        with open('dns_servers.txt', 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    self.servers.append(line)

        print(f"加载了 {len(self.servers)} 个 DNS 服务器")

    def load_domains_from_file(self):
        """从 domains.txt 加载待测试域名列表"""
        self.domains = []
        if not os.path.exists('domains.txt'):
            print("未找到 domains.txt 文件，使用默认域名 example.com")
            self.domains = ["example.com"]
            return

        with open('domains.txt', 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    self.domains.append(line)

        print(f"加载了 {len(self.domains)} 个待测试域名")

    def show_initial_tables(self):
        """在表格中显示初始 DNS 服务器和域名列表"""
        # 显示 DNS 服务器
        for server in self.servers:
            self.treeview.insert('', 'end', values=(server, "未测试"))

        # 显示域名
        for domain in self.domains:
            self.domain_treeview.insert('', 'end', values=(domain, "未测试"))

    def test_dns(self, server, domains):
        """测试单个 DNS 服务器对多个域名的响应时间，返回结果列表"""
        resolver = dns.resolver.Resolver()
        resolver.nameservers = [server]
        resolver.lifetime = 2  # 增加超时时间到 5 秒
        resolver.timeout = 2
        total_latency = 0.0  # 总响应时间
        success_count = 0  # 成功解析的数量
        domain_results = []

        for domain in domains:
            start = time.time()
            try:
                answers = resolver.resolve(domain, 'A')
                elapsed = time.time() - start
                total_latency += elapsed
                success_count += 1
                domain_results.append(f"{elapsed * 1000:.2f} ms")
                self.all_dns_results.append((server, domain, elapsed * 1000))  # 存储结果
                print(f"[成功] DNS 服务器: {server}, 域名: {domain}, 响应时间: {elapsed * 1000:.2f} ms")
            except dns.resolver.NXDOMAIN:
                domain_results.append("NXDOMAIN")
                print(f"[错误] 域名 {domain} 不存在 (NXDOMAIN)")
            except dns.resolver.NoNameservers:
                domain_results.append("NoNameservers")
                print(f"[错误] 无法解析域名 {domain} (NoNameservers)")
            except dns.resolver.Timeout:
                domain_results.append("超时")
                print(f"[错误] DNS 请求超时，服务器: {server}, 域名: {domain}")
            except Exception as e:
                domain_results.append("错误")
                print(f"[错误] 解析域名 {domain} 时发生未知错误: {e}")

        # 如果成功解析了至少一个域名，则计算平均响应时间
        if success_count > 0:
            avg_latency = total_latency / success_count
            return server, avg_latency, domain_results
        else:
            return server, float('inf'), domain_results

    def configure_tags(self):
        """配置颜色标签"""
        self.treeview.tag_configure('green', foreground='#008000')  # 绿色
        self.treeview.tag_configure('yellow', foreground='#FFD700')  # 金黄色
        self.treeview.tag_configure('orange', foreground='#FFA500')  # 橙色
        self.treeview.tag_configure('red', foreground='#FF0000')  # 红色

    def update_table(self, server, latency):
        """更新 DNS 表格中的单个条目"""
        for item in self.treeview.get_children():
            values = self.treeview.item(item, 'values')
            if values[0] == server:
                if latency == float('inf'):
                    self.treeview.set(item, 'latency', "超时")
                    self.treeview.item(item, tags=('red',))  # 添加标签
                else:
                    self.treeview.set(item, 'latency', f"{latency * 1000:.2f} ms")
                    if latency * 1000 < 50:
                        self.treeview.item(item, tags=('green',))
                    elif latency * 1000 < 200:
                        self.treeview.item(item, tags=('yellow',))
                    elif latency * 1000 < 500:
                        self.treeview.item(item, tags=('orange',))
                    else:
                        self.treeview.item(item, tags=('red',))
                break
        self.window.update_idletasks()  # 强制刷新界面

    def start_test_thread(self):
        """启动测试线程，并禁用输入框和按钮"""
        self.domain_entry.config(state='disabled')  # 禁用输入框
        self.test_btn.config(state='disabled')  # 禁用按钮
        threading.Thread(target=self.run_tests).start()

    def run_tests(self):
        """运行 DNS 服务器测试"""
        total_servers = len(self.servers)
        self.completed_tests = 0  # 重置已完成的测试数量
        self.results = []  # 清空结果列表
        self.all_dns_results = []  # 清空存储的结果

        # 根据用户选择的模式执行测试
        if self.test_mode.get() == 0:  # 单域名测试
            domain = self.test_domain.get()
            domains = [domain]  # 只测试输入框中的域名
        else:  # 多域名测试
            self.load_domains_from_file()  # 从文件加载域名
            domains = self.domains

        # 使用线程池并发测试
        with ThreadPoolExecutor(max_workers=10) as executor:
            for server in self.servers:
                future = executor.submit(self.test_dns, server, domains)
                future.add_done_callback(lambda f: self.process_result(f, domains, total_servers))

        # 等待所有线程完成
        while len(self.results) < total_servers:
            time.sleep(0.1)

        self.results.sort(key=lambda x: x[1])  # 按响应时间排序
        self.show_sorted_results(domains)
        self.calculate_domain_latencies(domains)  # 计算域名平均响应时间

        # 测试完成后重新启用输入框和按钮
        self.domain_entry.config(state='normal')
        self.test_btn.config(state='normal')

    def process_result(self, future, domains, total_servers):
        """处理线程池返回的结果"""
        server, latency, domain_results = future.result()
        self.results.append((server, latency))
        self.completed_tests += 1  # 更新已完成的测试数量
        self.update_progress(self.completed_tests, total_servers)  # 更新进度条和标签
        self.update_table(server, latency)  # 更新 DNS 表格

    def update_progress(self, current, total):
        """更新进度条和进度显示标签"""
        progress_value = int((current / total) * 100)
        self.progress['value'] = progress_value
        self.progress_label.config(text=f"进度: {current}/{total} ({progress_value}%)")
        self.window.update_idletasks()

    def show_sorted_results(self, domains):
        """清空表格并重新插入排序后的结果"""
        # 清空 DNS 表格
        for row in self.treeview.get_children():
            self.treeview.delete(row)

        # 插入排序后的结果，并设置颜色标签
        for server, latency in self.results:
            if latency == float('inf'):
                latency_str = "超时"
                tags = ('red',)
            else:
                latency_str = f"{latency * 1000:.2f} ms"
                if latency * 1000 < 50:
                    tags = ('green',)
                elif latency * 1000 < 200:
                    tags = ('yellow',)
                elif latency * 1000 < 500:
                    tags = ('orange',)
                else:
                    tags = ('red',)
            self.treeview.insert('', 'end', values=(server, latency_str), tags=tags)

    def calculate_domain_latencies(self, domains):
        """计算域名的平均响应时间"""
        for domain in domains:
            valid_responses = [
                result[2] for result in self.all_dns_results
                if result[1] == domain and result[2] < 50  # 响应时间小于50ms
            ]
            if valid_responses:
                avg_latency = sum(valid_responses) / len(valid_responses)
                latency_str = f"{avg_latency:.2f} ms"
            else:
                latency_str = "超时"

            for item in self.domain_treeview.get_children():
                values = self.domain_treeview.item(item, 'values')
                if values[0] == domain:
                    self.domain_treeview.set(item, 'latency', latency_str)
                    break


if __name__ == '__main__':
    app = DNSTester()
    app.window.mainloop()