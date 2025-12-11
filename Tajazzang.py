import os
import sys
from datetime import datetime
import tkinter as tk
from tkinter import messagebox
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import keyboard
import psutil
import pygetwindow as gw
import subprocess
import time
import logging
import win32gui
import win32process
import threading
import signal
import smtplib
from email.mime.text import MIMEText
import winsound

"""
Description:
- 이 코드는 Google Sheets API를 사용하여 퀴즈 데이터를 가져옵니다.
- 퀴즈 데이터는 Google Sheets의 특정 시트에서 가져옵니다.
- GUI는 tkinter를 사용하여 전체 화면 모드로 구현됩니다.
- 사용자는 한글 단어에 대한 영어 정답을 입력해야 합니다.

Quiz data format in Google Sheets:
| 한글 단어 | 영어 정답 | 힌트 |
=> https://docs.google.com/spreadsheets/d/1BHkAT3j75_jq5qM5p1AZ73NaR4JhcxP7uBeWZRE0CD8/edit?usp=sharing

exe 배포 : 
python -O -m PyInstaller --onefile --windowed `
    --add-data "tajazzang-credentials.json;." `
    --add-data "correct.wav;." `
    --add-data "wrong.wav;." `
    Tajazzang.py
"""
quiz_start_time = time.time()

# 로그 설정
# 로그 디렉터리 확인 및 생성
log_dir = r"C:\temp"
os.makedirs(log_dir, exist_ok=True)  # 폴더가 없으면 자동 생성

# 기존 로그 파일 삭제 (존재하는 경우)
log_file_path = os.path.join(log_dir, "log.txt")
if os.path.exists(log_file_path):
    try:
        os.remove(log_file_path)
    except OSError:
        pass  # 파일 삭제 실패 시 무시

# 로그 설정
logging.basicConfig(
    filename=log_file_path,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filemode="w",  # 쓰기 모드로 새 파일 생성
)


# quizapp 실행시 Windows 키 차단
def block_windows_key():
    keyboard.block_key("left windows")
    keyboard.block_key("right windows")


def unblock_windows_key():
    keyboard.unblock_key("left windows")
    keyboard.unblock_key("right windows")


def on_closing():
    # 프로세스 모니터링 중지
    process_monitor.stop_monitoring()
    unblock_windows_key()
    root.destroy()


# F1 키로 버전 정보 보기
def show_version():
    show_custom_message("버전 정보", "Tajazzang v0.0.1\n2025-12-08")
    # Tajazzang v0.0.1 : 초기 버전


# Google Sheets API 인증 설정
# 퀴즈 데이터와 메시지 템플릿을 한 번에 가져오기
def fetch_quiz_and_message():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]

    def resource_path(relative_path):
        if hasattr(sys, "_MEIPASS"):
            return os.path.join(sys._MEIPASS, relative_path)
        return os.path.join(os.path.abspath("."), relative_path)

    creds = ServiceAccountCredentials.from_json_keyfile_name(
        resource_path("tajazzang-credentials.json"), scope
    )
    client = gspread.authorize(creds)

    # 현재 날짜의 주차 정보 가져오기 (ISO 8601 기준)
    today = datetime.today()
    # isocalendar() returns (year, week_number, weekday)
    year, week_num, _ = today.isocalendar()
    sheet_name = f"Tajazzang_CW{week_num:02d}"  # CW50, CW51 형식
    try:
        sheet = client.open("Shooting").worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        messagebox.showerror(
            "시트 없음",
            f"{sheet_name} 시트가 존재하지 않습니다.\n(오늘: {today.strftime('%Y-%m-%d')}, {year}년 {week_num}주차)",
        )
        exit()

    data = sheet.get_all_records()
    quiz_data = []
    for row in data:
        proverb = row.get("속담", "").strip()
        if proverb:
            quiz_data.append(proverb)

    # 메시지 템플릿도 같이 가져오기
    COMMON_MSG = (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "다음 속담을 정확히 입력하세요({current_num}/{total_num}):\n\n"
        "'{korean_word}'"
    )
    msg_value = None
    hidden_code_value = None
    try:
        info_sheet = client.open("Shooting").worksheet("info_tajazzang")
        info_data = info_sheet.get_all_values()
        for row in info_data:
            if len(row) >= 2:
                key = row[0].strip().lower()
                value = row[1].strip()
                if key == "message":
                    msg_value = value
                elif key == "hidden code":
                    hidden_code_value = value
        if msg_value:
            message_template = msg_value + "\n\n" + COMMON_MSG
        else:
            raise Exception("msg 값 없음")
    except Exception as e:
        logging.error(f"info 시트에서 msg/hidden code 값 읽기 실패: {e}")
        message_template = (
            "우리 은기가 오늘 연습하는 타자 실력이\n"
            "언젠가 빠르고 정확한 타이핑으로 빛날 거야.\n\n"
            "매일매일 조금씩 연습하면서\n"
            "컴퓨터를 자유자재로 다루는 멋진 사람이 되는 거지.\n\n"
            "힘들어도 아빠가 끝까지 함께 할게!\n\n" + COMMON_MSG
        )

    return quiz_data, message_template, hidden_code_value


# 퀴즈 데이터 불러오기
quiz_data, quiz_message_template, exit_code = fetch_quiz_and_message()
current_index = 0

# 오답 리스트 및 정답 카운트 관리
wrong_list = []
total_attempts = 0
correct_count = 0
quiz_round = 1
initial_total_count = len(quiz_data)  # 최초 문제 개수 저장

# 라운드별 시도/정답 수 초기화
round_attempts = 0
round_correct = 0


# 메일 발송 함수
def send_wrong_list_email(wrong_list, elapsed_time=None):
    # 중복 제거
    unique_wrong_list = list(set(wrong_list))
    sender = "sungyong2010@gmail.com"
    receiver = ["sungyong2010@gmail.com", "seerazeene@gmail.com"]  # 여러 명을 리스트로
    password = "lbzx rzqb tszp geee"  # 앱 비밀번호 사용 권장
    subject = "Tajazzang 오답 리스트"
    body = "\n".join(unique_wrong_list)
    if elapsed_time is not None:
        h = int(elapsed_time // 3600)
        m = int((elapsed_time % 3600) // 60)
        s = int(elapsed_time % 60)
        time_str = f"{h:02d}:{m:02d}:{s:02d}"
        body = (
            "오답 리스트는 반복 학습할 수 있도록 구글 시트에 지속적으로 업데이트해 주세요.\n"
            f"[전체 수행시간: {time_str}]\n\n" + body
        )
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(receiver)  # 콤마로 연결된 문자열

    logging.info("메일 발송 시도: SMTP 연결 시작")
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            logging.info("SMTP 연결 성공, 로그인 시도")
            smtp.login(sender, password)
            logging.info("로그인 성공, 메일 발송 시도")
            smtp.sendmail(sender, receiver, msg.as_string())
        logging.info("오답 리스트 메일 발송 완료")
    except Exception as e:
        logging.error(f"메일 발송 실패: {e}")


# 누적 정답/시도 수를 별도 변수로 관리
total_attempts = 0
correct_count = 0

# 오답 리스트 및 정답 카운트 관리
wrong_list = []
all_wrong_list = []  # 모든 라운드의 오답을 누적


# 정답 확인 함수
def show_custom_message(title, message):
    popup = tk.Toplevel(root)
    popup.title(title)

    popup.configure(bg="black")
    popup.attributes("-topmost", True)

    # 화면 중앙에 위치
    window_width = 400
    window_height = 300
    screen_width = popup.winfo_screenwidth()
    screen_height = popup.winfo_screenheight()
    x = (screen_width - window_width) // 2
    y = (screen_height - window_height) // 2
    popup.geometry(f"{window_width}x{window_height}+{x}+{y}")

    # 모달 창으로 설정
    popup.transient(root)
    popup.grab_set()

    msg_label = tk.Label(
        popup,
        text=message,
        font=("맑은 고딕", 20),
        fg="white",
        bg="black",
        wraplength=350,
    )
    msg_label.pack(expand=True, pady=20)

    def close_popup():
        popup.grab_release()
        popup.destroy()
        entry.focus_set()  # 메인 창의 entry에 포커스 돌려주기

    ok_button = tk.Button(
        popup, text="확인", font=("맑은 고딕", 20), command=close_popup
    )
    ok_button.pack(pady=20)

    # ESC나 Enter키로도 창 닫기
    popup.bind("<Escape>", lambda e: close_popup())
    popup.bind("<Return>", lambda e: close_popup())

    # 포커스 설정
    ok_button.focus_set()

    # 창이 닫힐 때까지 대기
    popup.wait_window()


def check_answer(event=None):
    def resource_path(relative_path):
        if hasattr(sys, "_MEIPASS"):
            return os.path.join(sys._MEIPASS, relative_path)
        return os.path.join(os.path.abspath("."), relative_path)

    global current_index, correct_count, total_attempts, wrong_list, round_attempts, round_correct
    # Text 위젯에서 입력값 가져오기 (1.0부터 end-1c까지, 마지막 개행 제외)
    raw_input = entry.get("1.0", "end-1c")
    raw_answer = quiz_data[current_index]

    # 강력한 정규화: 모든 공백 제거 후 비교 (공백, 탭, 특수공백 등 모두 제거)
    import unicodedata

    # 1단계: 유니코드 정규화 (NFD -> NFC)
    user_input_nfc = unicodedata.normalize("NFC", raw_input)
    answer_nfc = unicodedata.normalize("NFC", raw_answer)

    # 2단계: 하이픈/대시 문자 정규화 (모든 종류의 하이픈을 일반 하이픈으로 통일)
    # U+002D: 일반 하이픈-마이너스 (-)
    # U+2013: En Dash (–)
    # U+2014: Em Dash (—)
    # U+2212: 마이너스 기호 (−)
    # U+FF0D: 전각 하이픈 (－)
    dash_chars = {
        "\u2013": "-",  # En Dash
        "\u2014": "-",  # Em Dash
        "\u2212": "-",  # Minus Sign
        "\uff0d": "-",  # Fullwidth Hyphen-Minus
    }
    for dash, replacement in dash_chars.items():
        user_input_nfc = user_input_nfc.replace(dash, replacement)
        answer_nfc = answer_nfc.replace(dash, replacement)

    # 3단계: 모든 종류의 공백 문자 제거
    user_input_clean = "".join(user_input_nfc.split())  # 모든 공백 제거
    answer_clean = "".join(answer_nfc.split())  # 모든 공백 제거

    # 4단계: 대소문자 정규화
    user_input_normalized = user_input_clean.lower()
    correct_answer_normalized = answer_clean.lower()

    # 디버그: 상세 로깅
    logging.info(f"=== 입력 분석 ===")
    logging.info(f"입력 원본: '{raw_input}' (길이: {len(raw_input)})")
    logging.info(f"입력 hex: {raw_input.encode('utf-8').hex()}")
    logging.info(
        f"입력 정규화: '{user_input_normalized}' (길이: {len(user_input_normalized)})"
    )
    logging.info(f"=== 정답 분석 ===")
    logging.info(f"정답 원본: '{raw_answer}' (길이: {len(raw_answer)})")
    logging.info(f"정답 hex: {raw_answer.encode('utf-8').hex()}")
    logging.info(
        f"정답 정규화: '{correct_answer_normalized}' (길이: {len(correct_answer_normalized)})"
    )
    logging.info(f"=== 비교 결과 ===")
    logging.info(f"일치 여부: {user_input_normalized == correct_answer_normalized}")

    # hidden code(=exit_code) 입력 시 즉시 종료
    if exit_code and user_input_clean == exit_code:
        show_custom_message("종료", "숨겨진 코드가 입력되어 프로그램을 종료합니다.")
        process_monitor.stop_monitoring()
        unblock_windows_key()
        root.destroy()
        sys.exit()

    round_attempts += 1
    total_attempts += 1

    # 정규화된 값으로 비교 (대소문자 무시, 공백 정규화)
    if user_input_normalized == correct_answer_normalized:
        round_correct += 1
        correct_count += 1
        # winsound.MessageBeep(winsound.MB_OK)
        # winsound.PlaySound("correct.wav", winsound.SND_FILENAME | winsound.SND_ASYNC)
        winsound.PlaySound(
            resource_path("correct.wav"), winsound.SND_FILENAME | winsound.SND_ASYNC
        )
        show_custom_message("정답", "정답입니다!")
    else:
        wrong_list.append(quiz_data[current_index])
        all_wrong_list.append(quiz_data[current_index])  # 모든 오답 누적
        # winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        # winsound.PlaySound("wrong.wav", winsound.SND_FILENAME | winsound.SND_ASYNC)
        winsound.PlaySound(
            resource_path("wrong.wav"), winsound.SND_FILENAME | winsound.SND_ASYNC
        )
        correct_answer_text = quiz_data[current_index]
        show_custom_message("오답", "오답입니다!")
        # 타자 연습을 하는 것임으로 힌트 제공 안함
        # if quiz_round < 3:
        #     show_custom_message("오답", "오답입니다!")
        # else:
        #     show_custom_message("오답", f"오답입니다!\n정답: {correct_answer_text}")

    current_index += 1
    if current_index >= len(quiz_data):
        process_quiz_end()
    else:
        update_question()  # 한 번만 호출


def process_quiz_end():
    global quiz_data, current_index, wrong_list, quiz_round, round_attempts, round_correct, initial_total_count
    # 전체 누적 정답율 계산 (초기 문제 개수 기준)
    accuracy = correct_count / initial_total_count if initial_total_count else 0
    elapsed_time = time.time() - quiz_start_time  # 수행시간 계산
    logging.info(
        f"퀴즈 종료 체크: 전체 시도={total_attempts}, 전체 정답={correct_count}, 정답율={accuracy:.3f}, 라운드={quiz_round}"
    )

    if accuracy >= 0.8:
        # send_wrong_list_email(wrong_list)
        send_wrong_list_email(
            all_wrong_list, elapsed_time
        )  # 모든 라운드의 오답을 메일로 발송, 수행시간 포함
        logging.info("정답율 80% 이상, 퀴즈 종료 및 메일 발송")
        show_custom_message(
            "성공!", f"정답율(누적): {accuracy*100:.1f}%\n퀴즈를 종료합니다."
        )
        process_monitor.stop_monitoring()
        unblock_windows_key()
        root.destroy()
        sys.exit()
    else:
        if not wrong_list:
            logging.info("오답 리스트 없음, 퀴즈 종료")
            show_custom_message(
                "종료",
                f"정답율(누적): {accuracy*100:.1f}%\n모든 문제를 맞추지 못했습니다. 퀴즈를 종료합니다.",
            )
            process_monitor.stop_monitoring()
            unblock_windows_key()
            root.destroy()
            sys.exit()
        else:
            quiz_data = wrong_list.copy()
            current_index = 0
            quiz_round += 1
            wrong_list = []
            # 라운드별 시도/정답 수 초기화
            round_attempts = 0
            round_correct = 0
            logging.info(
                f"오답 문제로 재도전: 라운드 {quiz_round}, 현재 정답율={accuracy:.3f}"
            )
            show_custom_message(
                "재도전",
                f"정답율(누적): {accuracy*100:.1f}%\n오답 문제로 다시 퀴즈를 진행합니다. (Round {quiz_round})",
            )
            update_question()


# 문제 업데이트
def update_question():
    # Text 위젯 내용 삭제 (1.0부터 end까지)
    entry.delete("1.0", tk.END)
    korean_word = quiz_data[current_index]

    # 현재 문제 번호와 전체 문제 수
    current_num = current_index + 1
    total_num = len(quiz_data)

    message = quiz_message_template.format(
        current_num=current_num, total_num=total_num, korean_word=korean_word
    )

    label.config(text=message)

    # 포커스 강제 설정 (지연 후 재적용)
    entry.focus_set()
    root.after(100, lambda: entry.focus_set())


# 디버그 모드 설정 (C언어의 #ifdef DEBUG와 유사)
# __debug__는 python -O로 실행시 False가 됨
DEBUG_MODE = __debug__


# 조기 프로세스 정리 (임포트 완료 즉시 실행)
def early_process_cleanup():
    """프로그램 로딩 중 조기 프로세스 정리"""
    try:
        # 간단한 프로세스 정리 (빠른 실행을 위해 최소화)
        unsafe_processes = [
            "cmd.exe",
            "notepad.exe",
            # , "explorer.exe"
        ]

        # DEBUG 모드가 아닌 경우에만 브라우저도 종료
        if not DEBUG_MODE:
            unsafe_processes.extend(
                ["chrome.exe", "firefox.exe", "msedge.exe", "powershell.exe"]
            )

        for proc in psutil.process_iter(["pid", "name"]):
            try:
                if proc.info["name"].lower() in unsafe_processes:
                    proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception:
        pass  # 에러 발생 시 무시하고 계속 진행


# 임포트 완료 즉시 조기 프로세스 정리 실행
early_process_cleanup()


# 포그라운드 프로세스 종료 함수 (먼저 정의)
def terminate_foreground_processes(safe_processes=None):
    if safe_processes is None:
        safe_processes = [
            "tajazzang.exe",
            "code.exe",
            "windowsterminal.exe",
            "wt.exe",
            "openonsole.exe",
            "explorer.exe",
            "totalcmd64.exe",
            "notepad++.exe",
        ]

        # DEBUG 모드에서만 chrome.exe 허용 (C언어 #ifdef DEBUG와 유사)
        if DEBUG_MODE:
            safe_processes.append("chrome.exe")
            safe_processes.append("vsclient.exe")
            safe_processes.append("powershell.exe")

    # 로블록스 프로세스는 무조건 종료 대상
    BLOCKED_PROCESSES = ["robloxplayerbeta.exe", "roblox.exe", "robloxstudio.exe"]

    # 현재 실행 중인 프로세스 이름도 보호
    current_process_name = psutil.Process(os.getpid()).name().lower()
    if current_process_name not in safe_processes:
        safe_processes.append(current_process_name)

    logging.info("### 포그라운드 프로세스 종료 시작")

    def enum_window_callback(hwnd, pid_list):
        if win32gui.IsWindowVisible(hwnd):
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                pid_list.add(pid)
            except Exception:
                pass

    visible_pids = set()
    win32gui.EnumWindows(enum_window_callback, visible_pids)

    for pid in visible_pids:
        try:
            proc = psutil.Process(pid)
            name = proc.name().lower()
            if name in BLOCKED_PROCESSES:
                proc.terminate()
                logging.info(f"로블록스 종료됨: {name} (PID: {pid})")
            if name not in safe_processes:
                proc.terminate()
                logging.info(f"종료됨: {name} (PID: {pid})")
            else:
                logging.info(f"유지됨: {name} (PID: {pid})")
        except Exception as e:
            logging.warning(f"종료 실패: PID {pid}, 오류: {e}")

    logging.info("### 포그라운드 프로세스 종료 완료")


# 백그라운드 프로세스 모니터링
class ProcessMonitor:
    def __init__(self):
        self.running = True
        self.monitor_thread = None

    def start_monitoring(self):
        """백그라운드에서 프로세스 모니터링 시작"""
        if not DEBUG_MODE:  # 릴리즈 모드에서만 모니터링
            self.monitor_thread = threading.Thread(
                target=self._monitor_loop, daemon=True
            )
            self.monitor_thread.start()

    def stop_monitoring(self):
        """프로세스 모니터링 중지"""
        self.running = False

    def _monitor_loop(self):
        """프로세스 모니터링 루프"""
        unsafe_processes = [
            "cmd.exe",
            "notepad.exe",
            "chrome.exe",
            "firefox.exe",
            "msedge.exe",
            # , "explorer.exe"
        ]
        # 로블록스 프로세스는 무조건 종료 대상
        BLOCKED_PROCESSES = ["robloxplayerbeta.exe", "roblox.exe", "robloxstudio.exe"]

        while self.running:
            try:
                for proc in psutil.process_iter(["pid", "name"]):
                    try:
                        if proc.info["name"].lower() in BLOCKED_PROCESSES:
                            proc.terminate()
                            logging.info(
                                f"모니터링: {proc.info['name']} 종료 (PID: {proc.info['pid']})"
                            )
                        if proc.info["name"].lower() in unsafe_processes:
                            proc.terminate()
                            logging.info(
                                f"모니터링: {proc.info['name']} 종료 (PID: {proc.info['pid']})"
                            )
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                time.sleep(2)  # 2초마다 체크
            except Exception as e:
                logging.warning(f"모니터링 오류: {e}")
                time.sleep(5)


# 프로세스 모니터 생성
process_monitor = ProcessMonitor()

# 전체 화면 GUI 설정
root = tk.Tk()
root.title("한글 → 영어 단어 퀴즈")
# 전체 화면 대신 최대화로 변경 (포커스 호환성 향상)
root.state("zoomed")  # 'zoomed'는 최대화 모드
root.overrideredirect(True)  # 타이틀바 및 최소/최대/닫기 버튼 제거
root.protocol("WM_DELETE_WINDOW", on_closing)
block_windows_key()
root.configure(bg="black")
root.attributes("-topmost", True)  # 창을 항상 최상위로 설정

# ✅ 포커스 강제 설정
root.focus_force()

# 프로그램 시작 즉시 프로세스 종료 (보안 강화)
logging.info("프로그램 시작 - 즉시 프로세스 정리 실행")
terminate_foreground_processes()
# 프로세스 종료 후 포커스 재설정
root.after(500, lambda: entry.focus_set())  # 500ms 지연 후 포커스

# 백그라운드 모니터링 시작
process_monitor.start_monitoring()
logging.info("백그라운드 프로세스 모니터링 시작")

# 예: F1 키로 버전 정보 보기
root.bind("<F1>", lambda event: show_version())

# 상단 프레임 (X 버튼용)
top_frame = tk.Frame(root, bg="black")
top_frame.pack(fill="x", side="top")


# X 버튼 (우상단) - DEBUG 모드에서만 표시
def close_app():
    # 프로세스 모니터링 중지
    process_monitor.stop_monitoring()
    on_closing()


# DEBUG 모드에서만 X 버튼 생성
if DEBUG_MODE:
    close_button = tk.Button(
        top_frame,
        text="✕",
        font=("Arial", 20),
        fg="white",
        bg="red",
        activebackground="darkred",
        command=close_app,
        width=3,
        height=1,
    )
    close_button.pack(side="right", padx=10, pady=5)

# 한글과 영어를 모두 지원하는 폰트로 라벨 생성
# 맑은 고딕은 Windows Vista 이상에 기본 설치되어 한글+영어+IME 모두 지원
label = tk.Label(root, text="", font=("맑은 고딕", 28), fg="white", bg="black")
label.pack(pady=80)


# 복사/붙여넣기 방지 함수
def disable_copy_paste(event):
    return "break"


# 엔터키로도 정답 제출 할 수 있도록...
# Text 위젯은 Entry보다 한글 IME를 더 잘 지원 (조합 중인 글자가 제대로 표시됨)
entry = tk.Text(
    root,
    font=("맑은 고딕", 24),
    height=1,
    width=70,
    relief="solid",
    bd=2,
    insertwidth=3,
    wrap="none",
    padx=8,
    pady=8,  # 내부 여백
    highlightthickness=0,
)  # 포커스 테두리 제거
entry.pack(pady=20, padx=20)

# IME 조합 윈도우 최적화 시도 (tkinter의 한계로 완벽하지 않음)
try:
    entry.configure(insertunfocussed="none")
except:
    pass


# 한글 조합 완성을 위한 약간의 지연 추가
def delayed_check_answer(event=None):
    # 한글 IME 조합이 완료될 시간을 주기 위해 100ms 지연
    root.after(100, lambda: check_answer())
    return "break"  # 기본 Enter 동작 방지 및 줄바꿈 방지


entry.bind("<Return>", delayed_check_answer)
entry.bind("<KP_Enter>", delayed_check_answer)  # 숫자패드 Enter도 지원

# 복사/붙여넣기 관련 단축키 차단
entry.bind("<Control-c>", disable_copy_paste)  # 복사 차단
entry.bind("<Control-v>", disable_copy_paste)  # 붙여넣기 차단
entry.bind("<Control-x>", disable_copy_paste)  # 잘라내기 차단
entry.bind("<Control-a>", disable_copy_paste)  # 전체 선택 차단


# 버튼을 클릭해서 정답 제출 할 수 있도록...
# 버튼 클릭 시에도 한글 조합 완성을 위한 지연 적용
def button_check_answer():
    entry.focus_set()  # 포커스를 Entry로 이동하여 IME 조합 완성
    root.after(150, lambda: check_answer())


button = tk.Button(
    root, text="정답 제출", font=("맑은 고딕", 20), command=button_check_answer
)
button.pack(pady=30)

# Entry 필드에 자동 포커스 설정
entry.focus_set()
root.after(200, lambda: entry.focus_set())  # 추가 지연 포커스


# Alt+F4 방지 (릴리즈 빌드에만 적용)
def disable_event():
    pass


# DEBUG 모드가 아닌 경우에만 Alt+F4 방지 적용
if not DEBUG_MODE:
    root.protocol("WM_DELETE_WINDOW", disable_event)
else:
    # DEBUG 모드에서는 정상적으로 창 닫기 허용
    root.protocol("WM_DELETE_WINDOW", on_closing)


# ✅ 시간 체크 함수 추가
def check_time_restriction():
    """새벽 12시부터 오전 8시 사이인지 체크"""
    current_time = datetime.now()
    current_hour = current_time.hour

    # 0시(자정)부터 9시 전까지는 실행 불가
    if 0 <= current_hour < 8:
        return False
    return True


if __name__ == "__main__":
    if not check_time_restriction():
        show_custom_message("Early Bird Bonus", "일찍 일어나는 새는 벌레를 잡는다!\n\n")
        unblock_windows_key()
        root.destroy()
        sys.exit()
    update_question()
    root.mainloop()
