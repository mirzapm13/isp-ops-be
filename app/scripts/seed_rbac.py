from app.config.database import SessionLocal
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User
from app.security.password import hash_password


PERMISSIONS = [
    "create_secret",
    "activate",
    "isolir",
    "open_isolir",
    "reconcile",
]


def seed():
    db = SessionLocal()

    try:
        # ---- Create Permissions ----
        permission_objs = {}
        for perm_name in PERMISSIONS:
            perm = db.query(Permission).filter_by(name=perm_name).first()
            if not perm:
                perm = Permission(name=perm_name)
                db.add(perm)
                db.flush()
            permission_objs[perm_name] = perm

        # ---- Create Roles ----
        superadmin = db.query(Role).filter_by(name="Superadmin").first()
        if not superadmin:
            superadmin = Role(name="Superadmin")
            db.add(superadmin)
            db.flush()

        technician = db.query(Role).filter_by(name="Technician").first()
        if not technician:
            technician = Role(name="Technician")
            db.add(technician)
            db.flush()

        # ---- Attach Permissions ----
        # Superadmin → all permissions
        superadmin.permissions = list(permission_objs.values())

        # Technician → only create_secret
        technician.permissions = [permission_objs["create_secret"]]

        super_user = db.query(User).filter_by(username="admin").first()
        if not super_user:
            super_user = User(
                username="admin",
                password_hash=hash_password("admin123")
            )
            super_user.roles.append(superadmin)
            db.add(super_user)

        db.commit()

        print("RBAC seeding completed successfully.")

        super_user = db.query(User).filter_by(username="admin").first()
        if not super_user:
            super_user = User(
                username="admin",
                password_hash=hash_password("admin123")
            )
            super_user.roles.append(superadmin)
            db.add(super_user)

    except Exception as e:
        db.rollback()
        print("Error during seeding:", e)
    finally:
        db.close()


if __name__ == "__main__":
    seed()