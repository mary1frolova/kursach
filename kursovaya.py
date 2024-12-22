import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
import random
from datetime import datetime, timedelta

# Инициализация данных
driver_list_type_a = []
driver_list_type_b = []
available_route_options = ['до конечной и обратно', 'до конечной']  # Изменённые названия типов маршрутов
shift_length_a = 8
shift_length_b = 12
travel_time_minutes = 60
workday_start_time = '06:00'
workday_end_time = '03:00'

# Функции логики
def check_weekend_day(selected_day):
    return selected_day in ['Суббота', 'Воскресенье']

def compute_route_end_time(start_time, route_time):
    start_time_obj = datetime.strptime(start_time, "%H:%M")
    end_time_obj = start_time_obj + timedelta(minutes=route_time)
    return end_time_obj.strftime("%H:%M")

def normalize_time_range(start_str, end_str):
    start = datetime.strptime(start_str, "%H:%M")
    end = datetime.strptime(end_str, "%H:%M")
    if end < start:
        end += timedelta(days=1)
    return start, end

def check_time_conflict(start_time, end_time, busy_times):
    s, e = normalize_time_range(start_time, end_time)
    for (bs, be) in busy_times:
        b_s, b_e = normalize_time_range(bs, be)
        if s < b_e and e > b_s:
            return True
    return False

def identify_available_slots(driver_busy_times, route_time, break_time):
    free_slots = []
    for driver, periods in driver_busy_times.items():
        normalized_periods = []
        for (st, ft) in periods:
            s_t, f_t = normalize_time_range(st, ft)
            normalized_periods.append((s_t, f_t))
        normalized_periods.sort(key=lambda x: x[0])
        current = datetime.strptime("06:00", "%H:%M")
        work_end = datetime.strptime("03:00", "%H:%M") + timedelta(days=1)
        for (st, et) in normalized_periods:
            if (st - current).total_seconds() / 60 >= route_time + break_time:
                free_slots.append((current.strftime("%H:%M"), st.strftime("%H:%M")))
            current = et
        if (work_end - current).total_seconds() / 60 >= route_time + break_time:
            free_slots.append((current.strftime("%H:%M"), work_end.strftime("%H:%M")))
    return free_slots

def compute_required_additional_drivers(num_routes, driver_list, shift_duration):
    max_routes_per_driver = int(shift_duration * 60 / travel_time_minutes)
    required_drivers = (num_routes + max_routes_per_driver - 1) // max_routes_per_driver
    if len(driver_list) >= required_drivers:
        return 0
    else:
        return required_drivers - len(driver_list)

def is_route_assignable(candidate_start_time, route_time, driver, driver_busy_times, driver_worked_hours,
                        driver_route_counts, min_break_time):
    candidate_end_time = compute_route_end_time(candidate_start_time, route_time)
    if check_time_conflict(candidate_start_time, candidate_end_time, driver_busy_times[driver]):
        return False
    if driver_busy_times[driver]:
        last_start, last_end = driver_busy_times[driver][-1]
        last_end_obj = datetime.strptime(last_end, "%H:%M")
        last_start_obj = datetime.strptime(last_start, "%H:%M")
        if last_end_obj < last_start_obj:
            last_end_obj += timedelta(days=1)
        candidate_start_obj = datetime.strptime(candidate_start_time, "%H:%M")
        if candidate_start_obj < last_end_obj:
            return False
        if (candidate_start_obj - last_end_obj).total_seconds() / 60 < min_break_time:
            return False
    worked_hours = driver_worked_hours[driver]
    if driver in driver_list_type_a and worked_hours >= shift_length_a:
        return False
    if driver in driver_list_type_b and worked_hours >= shift_length_b:
        return False
    candidate_end_obj = datetime.strptime(candidate_end_time, "%H:%M")
    if candidate_end_obj < datetime.strptime(candidate_start_time, "%H:%M"):
        candidate_end_obj += timedelta(days=1)
    end_work_obj = datetime.strptime("03:00", "%H:%M") + timedelta(days=1)
    if candidate_end_obj > end_work_obj:
        return False
    return True

def assign_route_to_available_driver(route_time, break_time, min_break_time, driver_list, driver_busy_times, driver_worked_hours,
                                     selected_day, driver_route_counts):
    # Сортировка водителей по количеству назначенных маршрутов (меньше назначений — предпочтительнее)
    sorted_drivers = sorted(driver_list, key=lambda d: driver_route_counts.get(d, 0))
    for _ in range(50):
        free_slots = identify_available_slots(driver_busy_times, route_time, break_time)
        if not free_slots:
            return None
        slot_start, slot_end = random.choice(free_slots)
        slot_start_obj = datetime.strptime(slot_start, "%H:%M")
        slot_end_obj = datetime.strptime(slot_end, "%H:%M")
        if slot_end_obj < slot_start_obj:
            slot_end_obj += timedelta(days=1)
        max_start = (slot_end_obj - slot_start_obj).total_seconds() / 60 - route_time
        if max_start < 0:
            continue
        offset = random.randint(0, int(max_start))
        candidate_start_obj = slot_start_obj + timedelta(minutes=offset)
        candidate_start = candidate_start_obj.strftime("%H:%M")
        for driver in sorted_drivers:
            if driver in driver_list_type_a and check_weekend_day(selected_day):
                continue
            if is_route_assignable(candidate_start, route_time, driver, driver_busy_times, driver_worked_hours,
                                   driver_route_counts, min_break_time):
                return (driver, candidate_start)
    return None

def attempt_genetic_schedule_creation(driver_list, shift_duration, num_routes, selected_day, break_time=10, min_break_time=30):
    available_drivers = list(driver_list)
    random.shuffle(available_drivers)
    driver_busy_times = {driver: [] for driver in available_drivers}
    driver_worked_hours = {driver: 0 for driver in available_drivers}
    driver_route_counts = {driver: 0 for driver in available_drivers}
    schedule = []
    start_time = datetime.strptime("06:00", "%H:%M")
    end_work_time = datetime.strptime("03:00", "%H:%M") + timedelta(days=1)
    for _ in range(num_routes):
        placed = False
        candidate_start_time = start_time
        candidate_end_time = candidate_start_time + timedelta(minutes=travel_time_minutes) 
        if candidate_end_time > end_work_time:
            route_type_selected = random.choice(available_route_options)
            route_type = f"{route_type_selected} (доп рейс)"
        else:
            route_type = random.choice(available_route_options)
        for driver in available_drivers:
            if is_route_assignable(candidate_start_time.strftime("%H:%M"), travel_time_minutes, driver,
                                   driver_busy_times, driver_worked_hours, driver_route_counts, min_break_time):
                schedule.append({
                    'Водитель': driver,
                    'Тип маршрута': route_type,
                    'Время начала': candidate_start_time.strftime("%H:%M"),
                    'Время окончания': candidate_end_time.strftime("%H:%M"),
                    'Маршрутов за смену': driver_route_counts[driver] + 1
                })
                driver_busy_times[driver].append((candidate_start_time.strftime("%H:%M"),
                                                  candidate_end_time.strftime("%H:%M")))
                driver_route_counts[driver] += 1
                driver_worked_hours[driver] += travel_time_minutes / 60
                placed = True
                break
        if not placed:
            result = assign_route_to_available_driver(travel_time_minutes, break_time, min_break_time, driver_list, driver_busy_times,
                                                     driver_worked_hours, selected_day, driver_route_counts)
            if result is None:
                break
            else:
                driver, slot_start = result
                cend = compute_route_end_time(slot_start, travel_time_minutes)
                worked_minutes = (datetime.strptime(cend, "%H:%M") - datetime.strptime(slot_start, "%H:%M")).seconds / 60
                schedule.append({
                    'Водитель': driver,
                    'Тип маршрута': f"{route_type} (доп рейс)",
                    'Время начала': slot_start,
                    'Время окончания': cend,
                    'Маршрутов за смену': driver_route_counts[driver] + 1
                })
                driver_busy_times[driver].append((slot_start, cend))
                driver_route_counts[driver] += 1
                driver_worked_hours[driver] += worked_minutes / 60
        start_time = candidate_end_time + timedelta(minutes=break_time)
        if start_time >= end_work_time:
            start_time = datetime.strptime("06:00", "%H:%M")
    return schedule, len(schedule)

def evaluate_schedule_fitness(schedule):
    num_routes = len(schedule)
    num_drivers_used = len(set(entry['Водитель'] for entry in schedule))
    # Вес для использования водителей установлен на 10, можно изменить по необходимости
    return num_routes + (num_drivers_used * 10)

def perform_crossover(parent1, parent2):
    if not parent1 or not parent2:
        return parent1, parent2
    crossover_point = len(parent1) // 2
    child1 = parent1[:crossover_point] + parent2[crossover_point:]
    child2 = parent2[:crossover_point] + parent1[crossover_point:]
    return child1, child2

def perform_mutation(schedule, driver_list, break_time=10):
    if not schedule:
        return schedule
    mutated_schedule = schedule.copy()
    mutation_point = random.randint(0, len(mutated_schedule) - 1)
    # Выбор водителя с наименьшим количеством назначенных маршрутов
    driver_route_counts = {}
    for entry in mutated_schedule:
        driver_route_counts[entry['Водитель']] = driver_route_counts.get(entry['Водитель'], 0) + 1
    sorted_drivers = sorted(driver_list, key=lambda d: driver_route_counts.get(d, 0))
    new_driver = sorted_drivers[0] if sorted_drivers else random.choice(driver_list)
    mutated_schedule[mutation_point]['Водитель'] = new_driver
    if random.random() < 0.5:
        original_start = mutated_schedule[mutation_point]['Время начала']
        original_end = mutated_schedule[mutation_point]['Время окончания']
        try:
            start_obj = datetime.strptime(original_start, "%H:%M") + timedelta(minutes=random.randint(-15, 15))
            end_obj = datetime.strptime(original_end, "%H:%M") + timedelta(minutes=random.randint(-15, 15))
            mutated_schedule[mutation_point]['Время начала'] = start_obj.strftime("%H:%M")
            mutated_schedule[mutation_point]['Время окончания'] = end_obj.strftime("%H:%M")
        except ValueError:
            pass  # Игнорируем ошибку форматирования времени
    return mutated_schedule

def show_generated_schedule(result_window, schedule_df, title_text="Итоговое расписание"):
    result_window.title(title_text)
    style = ttk.Style()
    style.configure("Treeview", background="#e0ffe0", foreground="black", rowheight=30, fieldbackground="#e0ffe0", bordercolor="#6b8e23", borderwidth=1)
    style.configure("Treeview.Heading", background="#228b22", foreground="white", font=("Arial", 12, "bold"))
    tree = ttk.Treeview(result_window, columns=list(schedule_df.columns), show='headings', height=15)
    for col in schedule_df.columns:
        tree.heading(col, text=col)
        tree.column(col, width=180, anchor='center')
    for _, row in schedule_df.iterrows():
        tree.insert('', tk.END, values=list(row))
    tree.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
    if schedule_df.empty:
        message = "Не удалось сгенерировать расписание.\nНужно добавить водителей или уменьшить число рейсов."
        messagebox.showerror("Ошибка", message)

def create_optimized_schedule(driver_list, shift_duration, num_routes, selected_day, parent_window, break_time=10,
                              min_break_time=30):
    additional_needed = compute_required_additional_drivers(num_routes, driver_list, shift_duration)
    if additional_needed > 0:
        message = f"Нехватка сотрудников.\nНужно добавить ещё {additional_needed} водителей или уменьшить число рейсов."
        messagebox.showerror("Ошибка", message)
        return
    schedule = []
    driver_busy_times = {d: [] for d in driver_list}
    driver_worked_hours = {d: 0 for d in driver_list}
    driver_route_counts = {d: 0 for d in driver_list}
    current_time = datetime.strptime("06:00", "%H:%M")
    work_end = datetime.strptime("03:00", "%H:%M") + timedelta(days=1)
    for _ in range(num_routes):
        route_type = random.choice(available_route_options)
        actual_time = travel_time_minutes * 2 if 'обратно' in route_type else travel_time_minutes  # Обновление логики для русских названий
        candidate_start_str = current_time.strftime("%H:%M")
        candidate_end_str = compute_route_end_time(candidate_start_str, actual_time)
        candidate_end_obj = datetime.strptime(candidate_end_str, "%H:%M")
        if candidate_end_obj < datetime.strptime(candidate_start_str, "%H:%M"):
            candidate_end_obj += timedelta(days=1)
        if candidate_end_obj > work_end:
            final_type = f"{route_type} (доп рейс)"
            result = assign_route_to_available_driver(actual_time, break_time, min_break_time, driver_list, driver_busy_times,
                                                     driver_worked_hours, selected_day, driver_route_counts)
            if result is None:
                message = "Расписание не утверждено.\nНужно добавить сотрудников или уменьшить число рейсов."
                messagebox.showerror("Ошибка", message)
                return
            else:
                driver, slot_start = result
                cend = compute_route_end_time(slot_start, actual_time)
                worked_minutes = (datetime.strptime(cend, "%H:%M") - datetime.strptime(slot_start, "%H:%M")).seconds / 60
                schedule.append({
                    'Водитель': driver,
                    'Тип маршрута': final_type,
                    'Время начала': slot_start,
                    'Время окончания': cend,
                    'Маршрутов за смену': driver_route_counts[driver] + 1
                })
                driver_busy_times[driver].append((slot_start, cend))
                driver_route_counts[driver] += 1
                driver_worked_hours[driver] += worked_minutes / 60
        else:
            placed = False
            copy_drivers = list(driver_list)
            random.shuffle(copy_drivers)
            for driver in copy_drivers:
                if driver in driver_list_type_a and check_weekend_day(selected_day):
                    continue
                if is_route_assignable(candidate_start_str, actual_time, driver, driver_busy_times, driver_worked_hours,
                                       driver_route_counts, min_break_time):
                    worked_minutes = (candidate_end_obj - datetime.strptime(candidate_start_str, "%H:%M")).seconds / 60
                    schedule.append({
                        'Водитель': driver,
                        'Тип маршрута': route_type,
                        'Время начала': candidate_start_str,
                        'Время окончания': candidate_end_str,
                        'Маршрутов за смену': driver_route_counts[driver] + 1
                    })
                    driver_busy_times[driver].append((candidate_start_str, candidate_end_str))
                    driver_route_counts[driver] += 1
                    driver_worked_hours[driver] += worked_minutes / 60
                    placed = True
                    current_time = candidate_end_obj + timedelta(minutes=break_time + min_break_time)
                    break
            if not placed:
                result = assign_route_to_available_driver(actual_time, break_time, min_break_time, driver_list, driver_busy_times,
                                                         driver_worked_hours, selected_day, driver_route_counts)
                if result is None:
                    message = "Расписание не утверждено.\nНужно добавить сотрудников или уменьшить число рейсов."
                    messagebox.showerror("Ошибка", message)
                    return
                else:
                    driver, slot_start = result
                    cend = compute_route_end_time(slot_start, actual_time)
                    worked_minutes = (datetime.strptime(cend, "%H:%M") - datetime.strptime(slot_start, "%H:%M")).seconds / 60
                    final_type = f"{route_type} (доп рейс)"
                    schedule.append({
                        'Водитель': driver,
                        'Тип маршрута': final_type,
                        'Время начала': slot_start,
                        'Время окончания': cend,
                        'Маршрутов за смену': driver_route_counts[driver] + 1
                    })
                    driver_busy_times[driver].append((slot_start, cend))
                    driver_route_counts[driver] += 1
                    driver_worked_hours[driver] += worked_minutes / 60
    result_window = tk.Toplevel(parent_window)
    df = pd.DataFrame(schedule)
    if not df.empty:
        show_generated_schedule(result_window, df, "Итоговое расписание:")
    else:
        show_generated_schedule(result_window, pd.DataFrame(), "Расписание не сформировано.")

def run_genetic_algorithm(driver_list, shift_duration, num_routes, selected_day, generations=50,
                          population_size=20, mutation_rate=0.1, break_time=10, min_break_time=30):
    population = []
    for _ in range(population_size):
        schedule, score = attempt_genetic_schedule_creation(driver_list, shift_duration, num_routes, selected_day,
                                                             break_time, min_break_time)
        population.append({'schedule': schedule, 'fitness': evaluate_schedule_fitness(schedule)})
    best_schedule = None
    best_fitness = -1
    for _ in range(generations):
        population = sorted(population, key=lambda x: x['fitness'], reverse=True)
        current_best = population[0]
        if current_best['fitness'] > best_fitness:
            best_fitness = current_best['fitness']
            best_schedule = current_best['schedule']
        if best_fitness >= num_routes + (len(driver_list) * 10):  # Условие остановки с учетом новых весов
            break
        parents = population[:population_size // 2]
        new_population = parents.copy()
        while len(new_population) < population_size:
            parent1, parent2 = random.sample(parents, 2)
            child1_schedule, child2_schedule = perform_crossover(parent1['schedule'], parent2['schedule'])
            child1 = {'schedule': child1_schedule, 'fitness': evaluate_schedule_fitness(child1_schedule)}
            child2 = {'schedule': child2_schedule, 'fitness': evaluate_schedule_fitness(child2_schedule)}
            new_population.extend([child1, child2])
        for individual in new_population:
            if random.random() < mutation_rate:
                mutated_schedule = perform_mutation(individual['schedule'], driver_list, break_time)
                individual['schedule'] = mutated_schedule
                individual['fitness'] = evaluate_schedule_fitness(mutated_schedule)
        population = new_population[:population_size]
    result_window = tk.Toplevel(root)
    if best_fitness >= num_routes + (len(driver_list) * 10):
        title_text = "Генетический алгоритм завершен. Лучшее расписание"
    else:
        title_text = "Генетический алгоритм завершен. Лучшее найденное расписание"
    if best_schedule and best_fitness > 0:
        df = pd.DataFrame(best_schedule)
        show_generated_schedule(result_window, df, f"{title_text} ({best_fitness} баллов):")
    else:
        show_generated_schedule(result_window, pd.DataFrame(), title_text)

def initiate_genetic_schedule():
    try:
        num_routes = int(number_of_routes_entry.get())
        selected_day = day_selection.get()
        all_drivers = driver_list_type_a + driver_list_type_b
        shift_duration = max(shift_length_a, shift_length_b)
        additional_needed = compute_required_additional_drivers(num_routes, all_drivers, shift_duration)
        if additional_needed > 0:
            message = f"Недостаточно водителей.\nДобавьте минимум {additional_needed} водителей или уменьшите число рейсов."
            messagebox.showerror("Ошибка", message)
            return
        if not driver_list_type_a and not driver_list_type_b:
            messagebox.showerror("Ошибка", "Нет водителей.")
            return
        if check_weekend_day(selected_day) and not driver_list_type_b:
            messagebox.showerror("Ошибка", "Выходной: Тип A не работает, а типа B нет.")
            return
        if check_weekend_day(selected_day) and not driver_list_type_a and driver_list_type_b:
            additional_b = compute_required_additional_drivers(num_routes, driver_list_type_b, shift_length_b)
            if additional_b > 0:
                message = f"Недостаточно водителей B на выходной. Нужно {additional_b}."
                messagebox.showerror("Ошибка", message)
                return
        run_genetic_algorithm(all_drivers, shift_duration, num_routes, selected_day,
                              generations=50, population_size=20, mutation_rate=0.1,
                              break_time=10, min_break_time=30)
    except ValueError:
        messagebox.showerror("Ошибка", "Не удалось сгенерировать: нужно добавить ещё водителей или уменьшить число рейсов.")

def initiate_schedule_generation():
    try:
        num_routes = int(number_of_routes_entry.get())
        selected_day = day_selection.get()
        all_drivers = driver_list_type_a + driver_list_type_b
        if not driver_list_type_a and not driver_list_type_b:
            messagebox.showerror("Ошибка", "Нет водителей.")
            return
        if check_weekend_day(selected_day) and not driver_list_type_b:
            messagebox.showerror("Ошибка", "Выходной: Тип A не работает, а типа B нет.")
            return
        if check_weekend_day(selected_day) and not driver_list_type_a and driver_list_type_b:
            additional_b = compute_required_additional_drivers(num_routes, driver_list_type_b, shift_length_b)
            if additional_b > 0:
                message = f"Недостаточно водителей B на выходной. Нужно {additional_b}."
                messagebox.showerror("Ошибка", message)
                return
            create_optimized_schedule(driver_list_type_b, shift_length_b, num_routes, selected_day, root)
            return
        max_shift = max(shift_length_a, shift_length_b)
        create_optimized_schedule(all_drivers, max_shift, num_routes, selected_day, root)
    except ValueError:
        messagebox.showerror("Ошибка", "Проверьте введенные данные.")

def switch_fullscreen_mode(event=None):
    root.attributes("-fullscreen", not root.attributes("-fullscreen"))
    return "break"

def leave_fullscreen_mode(event=None):
    root.attributes("-fullscreen", False)
    return "break"

# Создание основного окна с использованием `ttk` и `Notebook`
root = tk.Tk()
root.title("Daily Routes Planner")
root.geometry("1200x700")
root.configure(bg="#e0ffe0")  # Установим светло-зеленый фон для основного окна
root.bind("<F11>", switch_fullscreen_mode)
root.bind("<Escape>", leave_fullscreen_mode)

style = ttk.Style()
style.theme_use('clam')

# Определение переменной для цвета фона
bg_color = "#e0ffe0"  # Светло-зеленый цвет

# Настройка стилей с зеленой палитрой
# Стиль для фреймов
style.configure("Custom.TFrame", background=bg_color)

# Стиль для меток
style.configure("Custom.TLabel", background=bg_color)

# Стиль для полей ввода
style.configure("Custom.TEntry", fieldbackground=bg_color, foreground="black")
style.map("Custom.TEntry",
          background=[('focus', '#f0fff0')],  # При фокусе можно немного изменить цвет
          foreground=[('focus', 'black')])

# Настройка стилей вкладок
style.configure("TNotebook", background=bg_color)
style.configure("TNotebook.Tab", font=("Segoe UI", 12, "bold"), padding=[15, 10], background="#32cd32", foreground="white")
style.map("TNotebook.Tab",
          background=[("selected", "#66cdaa")],
          foreground=[("selected", "white")])

# Настройка стилей кнопок
style.configure("TButton",
                font=("Segoe UI", 14, "bold"),
                foreground="white",
                background="#32cd32",
                borderwidth=0,
                focusthickness=3,
                focuscolor='none',
                height=2,  # Увеличение высоты кнопок
                width=20)   # Увеличение ширины кнопок

# Добавление эффектов наведения для кнопок
def on_enter_hover(e):
    e.widget['background'] = '#66cdaa'

def on_leave_hover(e):
    e.widget['background'] = '#32cd32'

style.map("TButton",
          background=[("active", "#66cdaa")],
          foreground=[("active", "white")])

# Стиль для меток заголовков
style.configure("Header.TLabel",
                font=("Segoe UI", 20, "bold"),
                foreground="#006400",  # Темно-зеленый для заголовков
                background=bg_color)

# Создание Notebook (вкладок)
notebook = ttk.Notebook(root)
notebook.pack(expand=True, fill='both', padx=50, pady=50)  # Добавлены отступы для центрирования

# Вкладка "Регистрация водителей"
registration_tab = ttk.Frame(notebook, style="Custom.TFrame")
notebook.add(registration_tab, text="Регистрация водителей")

# Вкладка "Настройки маршрутов"
route_settings_tab = ttk.Frame(notebook, style="Custom.TFrame")
notebook.add(route_settings_tab, text="Настройки маршрутов")

# Вкладка "Генерация расписания"
schedule_generation_tab = ttk.Frame(notebook, style="Custom.TFrame")
notebook.add(schedule_generation_tab, text="Генерация расписания")

# Вкладка "Информация"
information_tab = ttk.Frame(notebook, style="Custom.TFrame")
notebook.add(information_tab, text="Информация")

# Регистрация водителей
# Заголовок
registration_header = ttk.Label(registration_tab, text="Внести водителя", style="Header.TLabel")
registration_header.pack(pady=20)

# Фрейм для ввода имени и категории водителя
registration_frame = ttk.Frame(registration_tab, padding=20, style="Custom.TFrame")
registration_frame.pack(pady=10)

# Ввод имени
ttk.Label(registration_frame, text="Имя водителя:", style="Custom.TLabel").grid(row=0, column=0, padx=10, pady=10, sticky='e')
driver_name_input = ttk.Entry(registration_frame, width=40, style="Custom.TEntry")  # Увеличение ширины поля ввода
driver_name_input.grid(row=0, column=1, padx=10, pady=10)

# Выбор категории водителя
ttk.Label(registration_frame, text="Категория водителя:", style="Custom.TLabel").grid(row=1, column=0, padx=10, pady=10, sticky='e')
driver_category = tk.StringVar()
driver_category.set("A")
driver_category_menu = ttk.Combobox(registration_frame, textvariable=driver_category, values=["A", "B"], state="readonly", width=38, style="Custom.TEntry")  # Увеличение ширины меню
driver_category_menu.grid(row=1, column=1, padx=10, pady=10)

# Кнопка внесения водителя
add_driver_btn = tk.Button(registration_tab, text="Внести водителя", command=lambda: add_driver(),
                          bg="#32cd32", fg="white", font=("Segoe UI", 14, "bold"), borderwidth=0, activebackground="#66cdaa")
add_driver_btn.pack(pady=20)

add_driver_btn.bind("<Enter>", on_enter_hover)
add_driver_btn.bind("<Leave>", on_leave_hover)

# Настройки маршрутов
# Заголовок
route_settings_header = ttk.Label(route_settings_tab, text="Настройки маршрутов", style="Header.TLabel")
route_settings_header.pack(pady=20)

# Фрейм для настройки маршрутов
route_settings_frame = ttk.Frame(route_settings_tab, padding=20, style="Custom.TFrame")
route_settings_frame.pack(pady=10)

# Количество маршрутов
ttk.Label(route_settings_frame, text="Число маршрутов за день:", style="Custom.TLabel").grid(row=0, column=0, padx=10, pady=10, sticky='e')
number_of_routes_entry = ttk.Entry(route_settings_frame, width=40, style="Custom.TEntry")  # Увеличение ширины поля ввода
number_of_routes_entry.grid(row=0, column=1, padx=10, pady=10)

# Продолжительность маршрута
ttk.Label(route_settings_frame, text="Продолжительность маршрута (мин):", style="Custom.TLabel").grid(row=1, column=0, padx=10, pady=10, sticky='e')
route_duration_entry = ttk.Entry(route_settings_frame, width=40, style="Custom.TEntry")  # Увеличение ширины поля ввода
route_duration_entry.grid(row=1, column=1, padx=10, pady=10)

# Кнопка применения настроек
apply_settings_btn = tk.Button(route_settings_tab, text="Применить настройки", command=lambda: apply_route_settings(),
                               bg="#32cd32", fg="white", font=("Segoe UI", 14, "bold"), borderwidth=0, activebackground="#66cdaa")
apply_settings_btn.pack(pady=20)

apply_settings_btn.bind("<Enter>", on_enter_hover)
apply_settings_btn.bind("<Leave>", on_leave_hover)

# Генерация расписания
# Заголовок
schedule_generation_header = ttk.Label(schedule_generation_tab, text="Создать расписание", style="Header.TLabel")
schedule_generation_header.pack(pady=20)

# Фрейм для генерации расписания
schedule_generation_frame = ttk.Frame(schedule_generation_tab, padding=20, style="Custom.TFrame")
schedule_generation_frame.pack(pady=10)

# Выбор дня
ttk.Label(schedule_generation_frame, text="Выберите день:", style="Custom.TLabel").grid(row=0, column=0, padx=10, pady=10, sticky='e')
day_selection = tk.StringVar()
day_selection.set("Понедельник")
day_selection_menu = ttk.Combobox(schedule_generation_frame, textvariable=day_selection, values=["Понедельник", "Вторник", "Среда", "Четверг",
                                                                                                   "Пятница", "Суббота", "Воскресенье"],
                                  state="readonly", width=38, style="Custom.TEntry")  # Увеличение ширины меню
day_selection_menu.grid(row=0, column=1, padx=10, pady=10)

# Кнопка создания расписания
create_schedule_btn = tk.Button(schedule_generation_tab, text="Создать расписание", command=lambda: initiate_schedule_generation(),
                                bg="#32cd32", fg="white", font=("Segoe UI", 14, "bold"), borderwidth=0, activebackground="#66cdaa")
create_schedule_btn.pack(pady=10)

create_schedule_btn.bind("<Enter>", on_enter_hover)
create_schedule_btn.bind("<Leave>", on_leave_hover)

# Кнопка генетического расписания
genetic_schedule_btn = tk.Button(schedule_generation_tab, text="Расписание методом генетического алгоритма", command=initiate_genetic_schedule,
                                 bg="#32cd32", fg="white", font=("Segoe UI", 14, "bold"), borderwidth=0, activebackground="#66cdaa")
genetic_schedule_btn.pack(pady=10)

genetic_schedule_btn.bind("<Enter>", on_enter_hover)
genetic_schedule_btn.bind("<Leave>", on_leave_hover)

# Кнопка сброса данных
reset_data_btn = tk.Button(route_settings_tab, text="Сбросить информацию", command=lambda: reset_all_data(),
                           bg="#32cd32", fg="white", font=("Segoe UI", 14, "bold"), borderwidth=0, activebackground="#66cdaa")
reset_data_btn.pack(pady=10)

reset_data_btn.bind("<Enter>", on_enter_hover)
reset_data_btn.bind("<Leave>", on_leave_hover)

# Информационная вкладка
# Заголовок
information_header = ttk.Label(information_tab, text="Сведения и Руководство", style="Header.TLabel")
information_header.pack(pady=20)

# Текст инструкции
information_text = (
    "Руководство:\n"
    "1. Перейдите во вкладку 'Регистрация водителей' и внесите водителей, выбрав их категорию (A или B).\n"
    "2. Перейдите во вкладку 'Настройки маршрутов', укажите число маршрутов и их продолжительность.\n"
    "3. Во вкладке 'Генерация расписания' выберите день и нажмите соответствующую кнопку для создания расписания.\n"
    "4. В случае ошибок или нехватки водителей система уведомит вас об этом.\n"
    "5. Используйте клавишу F11 для переключения полноэкранного режима.\n"
    "6. Нажмите Escape для выхода из полноэкранного режима.\n"
)
information_label = ttk.Label(information_tab, text=information_text, wraplength=800, justify="left", background=bg_color, foreground="black", font=("Segoe UI", 14))
information_label.pack(pady=10, padx=20)

# Информационный лейбл внизу основного окна
main_info_label = ttk.Label(root, text="", background=bg_color, foreground="#006400", font=("Segoe UI", 14))
main_info_label.pack(pady=10)

# Функция для обновления информационного лейбла
def update_main_info(message, color="#006400"):
    main_info_label.config(text=message, foreground=color)

# Функции для кнопок
def add_driver():
    name = driver_name_input.get().strip()
    category = driver_category.get()
    if not name:
        messagebox.showerror("Ошибка", "Введите имя водителя.")
        return
    if category == "A":
        driver_list_type_a.append(name)
    else:
        driver_list_type_b.append(name)
    driver_name_input.delete(0, tk.END)
    update_main_info(f"Водитель '{name}' добавлен.")

def reset_all_data():
    number_of_routes_entry.delete(0, tk.END)
    route_duration_entry.delete(0, tk.END)
    driver_name_input.delete(0, tk.END)
    update_main_info("Данные сброшены.")

def apply_route_settings():
    try:
        global travel_time_minutes
        travel_time_minutes = int(route_duration_entry.get())
        update_main_info(f"Продолжительность маршрута установлена на {travel_time_minutes} минут.")
    except ValueError:
        messagebox.showerror("Ошибка", "Введите корректное число для продолжительности маршрута.")

# Запуск основного цикла
root.mainloop()
