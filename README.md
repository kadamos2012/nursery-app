# نظام إدارة الحضانة — Backend (Flask)

## التشغيل محلياً
```bash
pip install -r requirements.txt
flask --app app.py seed      # ينشئ بيانات تجريبية
flask --app app.py run       # يشغل السيرفر على http://127.0.0.1:5000
```

بيانات الدخول التجريبية بعد الـ seed:
- **معلمة**: 01000000001 / teacher123 → صفحة الدخول الموحدة `/login`
- **ولية أمر**: 01000000002 / parent123 → عبر الـ API

## الموديلات (models.py)
Nursery → SchoolClass → Child ← ParentChild → Parent
كل طفل ليه: DailyLog (يومي)، AttendanceRecord (حضور)، Payment (مصروفات)، Message (رسائل)

## نقاط الـ API الجاهزة لواجهة الموبايل (React)
- `POST /api/auth/login` — تسجيل دخول (parent/teacher)
- `GET /api/parent/children` — أطفال ولي الأمر
- `GET /api/child/<id>/today` — تحديث النهاردة
- `GET /api/child/<id>/logs?limit=30` — السجل اليومي
- `GET /api/child/<id>/attendance?year=&month=` — الحضور
- `GET /api/child/<id>/payments` — المصروفات
- `GET|POST /api/child/<id>/messages` — الرسائل

كلهم بيرجعوا JSON ومحميين بـ session cookie (Flask-Login).

## صفحات المعلمة (server-rendered، سريعة على الموبايل)
- `/login` (صفحة دخول موحدة لكل الأدوار)
- `/teacher` — قائمة الأطفال وحالة تحديث كل واحد
- `/teacher/child/<id>/log` — نموذج تحديث سريع (اختيار بالضغط مش كتابة)

## الرفع على Render (خطوة بخطوة)

1. ارفعي المجلد ده كـ repo جديد على GitHub (زي `kadamos2012/nursery-app`)
2. في Render: **New → Web Service** واختاري الـ repo
3. الإعدادات:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
4. من تبويب **Environment**، ضيفي:
   - `SECRET_KEY` → أي نص عشوائي طويل
   - `DATABASE_URL` → هتتحط تلقائي لو عملتي Render Postgres (Dashboard → New → PostgreSQL) وربطتيه بالـ Web Service
   - `ALLOWED_ORIGIN` → سيبيها `*` مؤقتاً وقت التجربة (تقدري تحصريها بدومين محدد بعدين)
5. بعد أول Deploy، افتحي الـ Shell بتاع Render (أو أضيفي كـ Job) وشغلي:
   ```bash
   flask --app app.py db-init
   flask --app app.py seed   # مرة واحدة بس، للبيانات التجريبية
   ```
6. هياخدلك Render رابط زي `https://nursery-app-xxxx.onrender.com` — الرابط ده هو اللي تحطيه في زرار ⚙️ إعدادات السيرفر جوه تطبيق الموبايل (nursery-parent-app-connected.jsx)

**ملاحظة مهمة**: لو استخدمتي SQLite (من غير Postgres)، البيانات بتتمسح كل ما Render يعمل إعادة تشغيل للسيرفر. لازم Postgres عشان البيانات تفضل محفوظة.

## الخطوات الجاية بعد الرفع
1. تغيير بيانات الدخول التجريبية وحذف أمر `seed` أو تأمينه
2. رفع الصور: إضافة تخزين (S3 أو Render Disk) وربط `photo_url`
3. إشعارات فورية (Push Notifications) لما المعلمة تعمل تحديث
4. حصر `ALLOWED_ORIGIN` بدومين محدد بدل `*` قبل الإطلاق الفعلي
