# ⌨️ 타자짱 (Tajazzang) - 속담 타자 연습 프로그램

이 프로젝트는 Google Sheets API를 활용하여 실시간으로 속담 데이터를 불러오고, 사용자가 화면에 표시된 속담을 정확히 타이핑하는 전체 화면 타자 연습 프로그램입니다. 타자 실력 향상과 속담 학습을 동시에 할 수 있습니다.

---

## 🧩 주요 기능

- Google Sheets에서 실시간 속담 데이터 불러오기
- 주차별 시트 자동 선택 (`Tajazzang_CW50` 형식)
- 전체 화면 GUI (tkinter 기반)
- 정확히 입력해야 정답 처리 (띄어쓰기, 구두점 포함)
- 정답율 80% 이상 달성 시 종료
- 오답 문제 반복 학습 (최대 3라운드)
- 오답 리스트 이메일 자동 발송
- Alt+F4 차단 및 Windows 키 차단
- 새벽 12시~8시 실행 제한 (Early Bird Bonus)
- 정답/오답 사운드 효과
- 복사/붙여넣기 방지
- 엔터키로 정답 제출 가능

---

## 📄 Google Sheets 데이터 형식

| 속담 |
|------|
| 가는 말이 고와야 오는 말이 곱다 |
| 소 잃고 외양간 고친다 |
| 티끌 모아 태산 |
| 백지장도 맞들면 낫다 |
| ... |

- 시트 이름 형식: `Tajazzang_CW50`, `Tajazzang_CW51` (주차별)
  - CW = Calendar Week (ISO 8601 기준)
  - 예: 2025년 50주차 → `Tajazzang_CW50`
- 예시 문서: [속담 데이터 시트](https://docs.google.com/spreadsheets/d/1BHkAT3j75_jq5qM5p1AZ73NaR4JhcxP7uBeWZRE0CD8/edit?usp=sharing)

---

## 🛠️ 설치 및 실행 방법

### 1. 필수 패키지 설치
```bash
pip install gspread oauth2client keyboard psutil pygetwindow pywin32
```

### 2. Google Cloud 서비스 계정 설정
1. [Google Cloud Console](https://console.cloud.google.com/)에서 프로젝트 생성
2. Google Sheets API 활성화
3. 서비스 계정 생성 및 JSON 키 다운로드
4. `tajazzang-credentials.json`으로 저장

### 3. Google Sheets 준비
- 시트 이름: `Tajazzang_CW50` (현재 주차에 맞게)
- 컬럼: `속담` (단일 컬럼)
- `info` 시트 (선택사항):
  - `message`: 시작 메시지
  - `hidden code`: 비상 종료 코드

### 4. 사운드 파일 준비
- `correct.wav`: 정답 사운드
- `wrong.wav`: 오답 사운드

### 5. 실행
```bash
python Tajazzang.py
```

---

## 📦 EXE 배포

PyInstaller로 실행 파일 생성:

```powershell
python -O -m PyInstaller --onefile --windowed `
    --add-data "tajazzang-credentials.json;." `
    --add-data "correct.wav;." `
    --add-data "wrong.wav;." `
    Tajazzang.py
```

---

## 🎮 사용 방법

1. **프로그램 실행**: 전체 화면으로 시작
2. **속담 입력**: 화면에 표시된 속담을 정확히 타이핑
3. **정답 제출**: Enter 키 또는 "정답 제출" 버튼 클릭
4. **반복 학습**: 오답은 자동으로 재출제
5. **종료 조건**: 정답율 80% 이상 달성

### 단축키
- **F1**: 버전 정보 표시
- **ESC/Enter**: 팝업 창 닫기
- **Hidden Code**: 비상 종료 (info 시트에서 설정)

---

## ⚙️ 주요 설정

### 이메일 발송 설정
```python
sender = "your-email@gmail.com"
receiver = ["receiver1@gmail.com", "receiver2@gmail.com"]
password = "your-app-password"  # Gmail 앱 비밀번호
```

### 시간 제한 설정
```python
# 0시~8시 실행 제한
if 0 <= current_hour < 8:
    return False
```

### 디버그 모드
```bash
# 디버그 모드로 실행 (프로세스 종료 기능 비활성화, X 버튼 표시)
python Tajazzang.py

# 릴리즈 모드로 실행
python -O Tajazzang.py
```

---

## 📊 기능 상세

### 정답율 계산
- 전체 시도 횟수 대비 정답 횟수
- 80% 이상: 프로그램 종료 및 오답 메일 발송
- 80% 미만: 오답 문제로 재도전

### 라운드 시스템
- **Round 1**: 전체 문제
- **Round 2**: Round 1 오답 문제
- **Round 3**: Round 2 오답 문제 (정답 표시)

### 프로세스 관리
- 차단 프로세스: 로블록스, 브라우저, cmd, notepad 등
- 백그라운드 모니터링: 2초마다 체크
- 디버그 모드에서는 개발 도구 허용

---

## 📝 버전 히스토리

- **v0.0.1** (2025-12-08): 초기 버전 (타자 연습 프로그램으로 전환)

---

## 🔧 업데이터 프로그램

`TajazzangUpdater.py`를 통해 자동 업데이트 지원:
- GitHub에서 최신 버전 확인
- 자동 다운로드 및 설치
- 백업 생성
- 작업 스케줄러 연동

```powershell
python -O -m PyInstaller --onefile `
    --noconsole `
    --name TajazzangUpdater `
    TajazzangUpdater.py
```

---

## 📄 라이선스

이 프로젝트는 개인 교육용 프로젝트입니다.

---

## 🙋 문의

문제가 발생하거나 제안사항이 있으면 이슈를 등록해주세요!
