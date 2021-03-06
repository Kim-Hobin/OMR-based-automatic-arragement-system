# recognition_modules.py
import functions as fs
import cv2


# 1. 조표 인식 함수
# ======================================================================================================================
'''
1. 조표는 첫 번째 객체인 음자리표 뒤 두 번째 객체로 위치해 있다.
2. 하지만 다 장조의 경우 조표가 없기 때문에 조표가 있을 위치에 박자표가 위치 해있다.
3, 두 번째 객체가 확실하게 박자표라면 해당 악곡은 다장조이다.
4. 플랫과 샾은 처음 탐색되는 기둥(stem)의 y 좌표를 통해 분류할 수 있다.
'''
# ======================================================================================================================
def recognize_key(image, staves, stats):
    (x, y, w, h, area) = stats
    ts_conditions = (
            staves[0] + fs.weighted(5) >= y >= staves[0] - fs.weighted(5) and  # 상단 위치 조건
            staves[4] + fs.weighted(5) >= y + h >= staves[4] - fs.weighted(5) and  # 하단 위치 조건
            staves[2] + fs.weighted(5) >= fs.get_center(y, h) >= staves[2] - fs.weighted(5) and  # 중단 위치 조건
            fs.weighted(18) >= w >= fs.weighted(10) and  # 넓이 조건
            fs.weighted(45) >= h >= fs.weighted(35)  # 높이 조건
    )
    if ts_conditions:
        return True, 0
    else:  # 조표가 있을 경우 (다장조를 제외한 모든 조)
        stems = fs.stem_detection(image, stats, 20)
        if stems[0][0] - x >= fs.weighted(3):  # 직선이 나중에 발견되면
            key = int(10 * len(stems) / 2)  # 샾
        else:  # 직선이 일찍 발견되면
            key = 100 * len(stems)  # 플랫

    return False, key


# 2. 음표 인식 함수
# ======================================================================================================================
'''
1. 음표는 객체에서 추출할 수 있는 여러 특징점들을 조합해 분류할 수 있다.
2. 음표로 추정되는 객체를 분류하기 위해선 4가지 특징점들을 추출해야 한다.
3. 각 머리(head), 기둥(stem), 꼬리(tail), 점(dot)이다.
'''
# ======================================================================================================================
def recognize_note(image, staff, stats, stems, direction):
    (x, y, w, h, area) = stats
    notes = []
    pitches = []
    note_condition = (
            len(stems) and
            w >= fs.weighted(10) and  # 넓이 조건
            h >= fs.weighted(35) and  # 높이 조건
            area >= fs.weighted(95)  # 픽셀 갯수 조건
    )
    if note_condition:
        for i in range(len(stems)):
            stem = stems[i]
            head_exist, head_fill, head_center = recognize_note_head(image, stem, direction)
            if head_exist:
                tail_cnt = recognize_note_tail(image, i, stem, direction)
                dot_exist = recognize_note_dot(image, stem, direction, len(stems), tail_cnt)
                note_classification = (
                    ((not head_fill and tail_cnt == 0 and not dot_exist), 2),
                    ((not head_fill and tail_cnt == 0 and dot_exist), -2),
                    ((head_fill and tail_cnt == 0 and not dot_exist), 4),
                    ((head_fill and tail_cnt == 0 and dot_exist), -4),
                    ((head_fill and tail_cnt == 1 and not dot_exist), 8),
                    ((head_fill and tail_cnt == 1 and dot_exist), -8),
                    ((head_fill and tail_cnt == 2 and not dot_exist), 16),
                    ((head_fill and tail_cnt == 2 and dot_exist), -16),
                    ((head_fill and tail_cnt == 3 and not dot_exist), 32),
                    ((head_fill and tail_cnt == 3 and dot_exist), -32)
                )

                for j in range(len(note_classification)):
                    if note_classification[j][0]:
                        note = note_classification[j][1]
                        pitch = recognize_pitch(image, staff, head_center)
                        notes.append(note)
                        pitches.append(pitch)
                        fs.put_text(image, note, (stem[0] - fs.weighted(10), stem[1] + stem[3] + fs.weighted(30)))
                        fs.put_text(image, pitch, (stem[0] - fs.weighted(10), stem[1] + stem[3] + fs.weighted(60)))
                        break

    return notes, pitches


# 2-1. 음표 머리 인식 함수
# ======================================================================================================================
'''
1. 음표의 머리는 음표의 기둥(stem) 위치를 이용해 탐색해볼 수 있다.
2. 정 방향 음표는 음표의 기둥 왼쪽 아래, 역 방향 음표는 음표의 기둥 오른쪽 위에 존재한다.
3, 해당 부분을 히스토그램을 통해 탐색한다면 머리가 존재하는지, 존재한다면 채워져 있는지 비었는지 분류할 수 있다.
'''
# ======================================================================================================================
def recognize_note_head(image, stem, direction):
    (x, y, w, h) = stem
    if direction:  # 정 방향 음표
        area_top = y + h - fs.weighted(7)  # 음표 머리를 탐색할 위치 (상단)
        area_bot = y + h + fs.weighted(7)  # 음표 머리를 탐색할 위치 (하단)
        area_left = x - fs.weighted(14)  # 음표 머리를 탐색할 위치 (좌측)
        area_right = x  # 음표 머리를 탐색할 위치 (우측)
    else:  # 역 방향 음표
        area_top = y - fs.weighted(7)  # 음표 머리를 탐색할 위치 (상단)
        area_bot = y + fs.weighted(7)  # 음표 머리를 탐색할 위치 (하단)
        area_left = x + w  # 음표 머리를 탐색할 위치 (좌측)
        area_right = x + w + fs.weighted(14)  # 음표 머리를 탐색할 위치 (우측)

    cnt = 0  # cnt = 끊기지 않고 이어져 있는 선의 개수를 셈
    cnt_max = 0  # cnt_max = cnt 중 가장 큰 값
    head_center = 0
    pixel_cnt = fs.count_rect_pixels(image, (area_left, area_top, area_right - area_left, area_bot - area_top))

    for row in range(area_top, area_bot):
        col, pixels = fs.get_line(image, fs.HORIZONTAL, row, area_left, area_right, 5)
        pixels += 1
        if pixels >= fs.weighted(5):
            cnt += 1
            cnt_max = max(cnt_max, pixels)
            head_center += row

    head_exist = (cnt >= 3 and pixel_cnt >= 50)
    head_fill = (cnt >= 8 and cnt_max >= 9 and pixel_cnt >= 80)
    head_center /= cnt

    return head_exist, head_fill, head_center


# 2-2. 음표 꼬리 인식 함수
# ======================================================================================================================
'''
1. 음표의 꼬리는 음표의 기둥(stem) 위치를 이용해 탐색해볼 수 있다.
2. 정 방향 음표는 음표의 기둥 오른쪽 위에, 역 방향 음표는 음표의 기둥 오른쪽 아래에 존재한다.
3. 해당 부분을 히스토그램을 통해 탐색한다면 꼬리가 존재하는지, 존재한다면 몇개가 있는지 분류할 수 있다.
'''
# ======================================================================================================================
def recognize_note_tail(image, index, stem, direction):
    (x, y, w, h) = stem
    if direction:  # 정 방향 음표
        area_top = y  # 음표 꼬리를 탐색할 위치 (상단)
        area_bot = y + h - fs.weighted(15)  # 음표 꼬리를 탐색할 위치 (하단)
    else:  # 역 방향 음표
        area_top = y + fs.weighted(15)  # 음표 꼬리를 탐색할 위치 (상단)
        area_bot = y + h  # 음표 꼬리를 탐색할 위치 (하단)
    if index:
        area_col = x - fs.weighted(4)  # 음표 꼬리를 탐색할 위치 (열)
    else:
        area_col = x + w + fs.weighted(4)  # 음표 꼬리를 탐색할 위치 (열)

    cnt = fs.count_pixels_part(image, area_top, area_bot, area_col)

    return cnt


# 2-3. 음표 점 인식 함수
# ======================================================================================================================
'''
1. 음표의 점은 음표의 기둥(stem) 위치를 이용해 탐색해볼 수 있다.
2. 정 방향 음표는 음표의 기둥 오른쪽 아래에, 역 방향 음표는 음표의 기둥 오른쪽 위에 존재한다.
3. 해당 부분을 탐색해 픽셀의 개수를 살펴보면 점이 존재하는지 알 수 있다.
'''
# ======================================================================================================================
def recognize_note_dot(image, stem, direction, stems_cnt, tail_cnt):
    (x, y, w, h) = stem
    if direction:  # 정 방향 음표
        area_top = y + h - fs.weighted(10)  # 음표 점을 탐색할 위치 (상단)
        area_bot = y + h + fs.weighted(5)  # 음표 점을 탐색할 위치 (하단)
        area_left = x + w + fs.weighted(2)  # 음표 점을 탐색할 위치 (좌측)
        area_right = x + w + fs.weighted(12)  # 음표 점을 탐색할 위치 (우측)
    else:  # 역 방향 음표
        area_top = y - fs.weighted(10)  # 음표 점을 탐색할 위치 (상단)
        area_bot = y + fs.weighted(5)  # 음표 점을 탐색할 위치 (하단)
        area_left = x + w + fs.weighted(14)  # 음표 점을 탐색할 위치 (좌측)
        area_right = x + w + fs.weighted(24)  # 음표 점을 탐색할 위치 (우측)
    dot_rect = (
        area_left,
        area_top,
        area_right - area_left,
        area_bot - area_top
    )

    pixels = fs.count_rect_pixels(image, dot_rect)

    threshold = (10, 15, 20, 30)
    if direction and stems_cnt == 1:
        return pixels >= fs.weighted(threshold[tail_cnt])
    else:
        return pixels >= fs.weighted(threshold[0])


# 2-4. 음 높낮이 인식 함수
# ======================================================================================================================
'''
1. 음의 높낮이는 음표머리의 위치와 오선의 좌표를 비교하면 쉽게 알 수 있다.
2. 정 방향 음표의 경우 음표 기둥의 하단, 역 방향 음표의 경우 음표 기둥의 상단이 음표 머리의 중단 y 좌표이다.
'''
# ======================================================================================================================
def recognize_pitch(image, staff, head_center):
    pitch_lines = [staff[4] + fs.weighted(30) - fs.weighted(5) * i for i in range(21)]

    for i in range(len(pitch_lines)):
        line = pitch_lines[i]
        if line + fs.weighted(2) >= head_center >= line - fs.weighted(2):
            return i


# 3. 쉼표 인식 함수
# ======================================================================================================================
'''
1. 쉼표는 보표에서 항상 고정된 위치에 있기 때문에, 이를 이용해 쉽게 분류할 수 있다.
2. 픽셀의 개수 등 다양한 조건을 추가해 좀 더 엄격하게 탐색할 수 있다.
'''
# ======================================================================================================================
def recognize_rest(image, staff, stats):
    (x, y, w, h, area) = stats
    rest = 0
    center = fs.get_center(y, h)
    rest_condition = staff[3] > center > staff[1]
    if rest_condition:
        cnt = fs.count_pixels_part(image, y, y + h, x + fs.weighted(1))
        if fs.weighted(35) >= h >= fs.weighted(25):
            if cnt == 3 and fs.weighted(11) >= w >= fs.weighted(7):
                rest = 4
            elif cnt == 1 and fs.weighted(14) >= w >= fs.weighted(11):
                rest = 16
        elif fs.weighted(22) >= h >= fs.weighted(16):
            if fs.weighted(15) >= w >= fs.weighted(9):
                rest = 8
        elif fs.weighted(8) >= h:
            if staff[1] + fs.weighted(5) >= center >= staff[1]:
                rest = 1
            elif staff[2] >= center >= staff[1] + fs.weighted(5):
                rest = 2
        if recognize_rest_dot(image, stats):
            rest *= -1
        if rest:
            fs.put_text(image, rest, (x, y + h + fs.weighted(30)))
            fs.put_text(image, -1, (x, y + h + fs.weighted(60)))

    return rest


def recognize_rest_dot(image, stats):
    (x, y, w, h, area) = stats
    area_top = y - fs.weighted(10)  # 쉼표 점을 탐색할 위치 (상단)
    area_bot = y + fs.weighted(10)  # 쉼표 점을 탐색할 위치 (하단)
    area_left = x + w  # 쉼표 점을 탐색할 위치 (좌측)
    area_right = x + w + fs.weighted(10)  # 쉼표 점을 탐색할 위치 (우측)
    dot_rect = (
        area_left,
        area_top,
        area_right - area_left,
        area_bot - area_top
    )

    pixels = fs.count_rect_pixels(image, dot_rect)

    return pixels >= fs.weighted(10)


def recognize_whole_note(image, staff, stats):
    whole_note = 0
    pitch = 0
    (x, y, w, h, area) = stats
    while_note_condition = (
            fs.weighted(22) >= w >= fs.weighted(12) >= h >= fs.weighted(9)
    )
    if while_note_condition:
        dot_rect = (
            x + w,
            y - fs.weighted(10),
            fs.weighted(10),
            fs.weighted(20)
        )
        pixels = fs.count_rect_pixels(image, dot_rect)
        whole_note = -1 if pixels >= fs.weighted(10) else 1
        pitch = recognize_pitch(image, staff, fs.get_center(y, h))

        fs.put_text(image, whole_note, (x, y + h + fs.weighted(30)))
        fs.put_text(image, pitch, (x, y + h + fs.weighted(60)))

    return whole_note, pitch
