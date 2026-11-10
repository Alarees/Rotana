# وكيل ميزان روتانا — نسخة Firebird 2.5

يقرأ تذاكر SmartBridge من قاعدة Firebird (قراءة فقط) ويرسلها إلى موديول أودو `rotana_weighbridge`.
لا يعدّل قاعدة الميزان أبدًا، ولا يحتاج لتصدير ملفات، ولا يستخدم n8n.

## كيف يعمل
- كل دقيقة: يقرأ تذاكر آخر 30 يومًا (والمعلّقة) ويقارنها بما أكّده أودو سابقًا، ويرسل **الجديد والمعدَّل فقط**.
- إذا انقطع الإنترنت أو توقف أودو: لا يضيع شيء؛ التذاكر غير المؤكَّدة تُعاد تلقائيًا في الدورة التالية.
- التذكرة المحذوفة من الميزان تُعلَّم "ملغاة" في أودو. وإن اختفى أكثر من 20 تذكرة دفعة واحدة (أرشفة مثلًا) لا يلغي شيئًا ويكتب تحذيرًا في السجل.
- الأوقات تُحوَّل من توقيت الجهاز المحلي إلى UTC (`utc_offset_minutes`، السودان = 120).

## المتطلبات
- ويندوز، وعلى **نفس الجهاز الذي يشغّل خادم Firebird الخاص بـ SmartBridge** (أو جهاز يصل إليه عبر الشبكة، غيّر `host`).
- Python، مثبّت **لكل المستخدمين** (Install for all users) ومضاف إلى PATH.
- **Python 3.8** (آخر إصدار يعمل على Windows 7) أو أحدث. المكتبة المستخدمة `fdb`.
- **يجب أن يطابق Python (32 أو 64 بت) ملف `fbclient.dll` الخاص بـ Firebird 2.5** — غالبًا 32 بت، فثبّت Python 32 بت.
- مكان العميل عادةً: `C:\Program Files (x86)\Firebird\Firebird_2_5\bin\fbclient.dll`.

## التثبيت خطوة بخطوة
1. انسخ هذا المجلد إلى `C:\RotanaWBAgent`.
2. افتح CMD داخله ونفّذ: `pip install -r requirements.txt`
3. **مستخدم القراءة:** عدّل كلمة المرور داخل `grant_reader.sql` ثم نفّذ من مجلد Firebird:
   `isql -user SYSDBA -password <كلمة سر SYSDBA> localhost/3052:SMARTBRIDGE -i C:\RotanaWBAgent\grant_reader.sql`
4. انسخ `config.ini.example` إلى `config.ini` وأدخل بيانات Firebird وأودو (الرابط والمفتاح `rotana_weighbridge.api_token`).
5. `python agent.py check` — يفحص الاتصال بـ Firebird وأودو ويطبع **إصدار Firebird** الفعلي. يجب أن تظهر كلها `[ OK ]`.
6. `python agent.py once --dry-run` — يعرض ما سيُرسل دون إرسال.
7. `python agent.py full` — الاستيراد الأول لكل التذاكر (حوالي 4,600 تذكرة).
8. شغّل `install_task.bat` **كمسؤول** ليعمل الوكيل تلقائيًا عند كل إقلاع. السجل في `logs\agent.log`.

## تغيير مستخدم القراءة أو كلمة سره
عدّل `user` و`password` في `[firebird]` داخل `config.ini` ثم أعد تشغيل المهمة (أو الجهاز). لا حاجة لتعديل أي كود.
لإنشاء مستخدم آخر: غيّر الاسم داخل `grant_reader.sql` ونفّذه. ولتغيير كلمة السر فقط: `ALTER USER SB_READER PASSWORD 'new';`
ويمكن بدلًا من الملف استخدام متغيري البيئة `WB_FB_USER` و`WB_FB_PASSWORD` و`WB_ODOO_TOKEN`.

## الأوامر
| الأمر | الوظيفة |
|---|---|
| `python agent.py check` | فحص البيئة وطباعة إصدار Firebird |
| `python agent.py once --dry-run` | يعرض ما سيُرسل فقط |
| `python agent.py once` | دورة واحدة |
| `python agent.py full` | يعيد إرسال كل التذاكر |
| `python agent.py run` | تشغيل مستمر (تبدؤه المهمة المجدولة) |

## مشاكل شائعة
- **`cannot load fbclient` / `Error loading`:** عدم تطابق 32/64 بت بين Python و`fbclient.dll`. ثبّت Python بنفس البتات، أو حدّد `client_library` في الإعدادات.
- **`Your user name and password are not defined`:** المستخدم غير موجود أو كلمة السر خطأ، أعد تنفيذ `grant_reader.sql`.
- **`Odoo rejected the token`:** المفتاح في `config.ini` لا يطابق `rotana_weighbridge.api_token` في أودو.
- **يعمل من CMD ولا يعمل من المهمة المجدولة:** Python مثبّت لمستخدم واحد فقط. ثبّته لكل المستخدمين وأعد `pip install`.
- **أرقام التذاكر عادت إلى 1 بعد أرشفة:** غيّر `station` (مثل `main-2`) في `config.ini` ثم `python agent.py full`.
- **المراقبة:** `state\heartbeat.txt` يحوي وقت آخر دورة ناجحة.
