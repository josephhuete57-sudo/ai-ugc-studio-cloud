import sqlite3
for db in (r'C:\AI_UGC_STUDIO\app\studio.db',):
    try:
        c = sqlite3.connect(db)
        c.execute(
            "UPDATE jobs SET status='cancelled', step='Cancelado (bug stderr anterior)' "
            "WHERE status='running' AND id IN (3)"
        )
        c.commit()
        print('ZOMBIE_FIXED', db)
    except Exception as e:
        print('ZOMBIE_SKIP', e)
