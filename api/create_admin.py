"""
Crée un compte administrateur, ou donne le rôle admin à un compte existant.
Le mot de passe est demandé au clavier (jamais en argument ni dans l'historique).

Sur le serveur :
    docker compose exec api python -m api.create_admin ton@email.com
"""
import getpass
import sys

from godata import init_db
from godata.repos import UserRepo
from .auth import hash_password


def main(argv: list[str]) -> int:
    if len(argv) != 2 or "@" not in argv[1]:
        print("Usage : python -m api.create_admin ton@email.com")
        return 1
    email = argv[1].strip()
    init_db()
    user = UserRepo.get_by_email(email)
    if user is None:
        password = getpass.getpass("Mot de passe (8 caractères min) : ")
        if len(password) < 8:
            print("❌ Mot de passe trop court")
            return 1
        if getpass.getpass("Confirme le mot de passe : ") != password:
            print("❌ Les mots de passe ne correspondent pas")
            return 1
        user = UserRepo.create(email, hash_password(password))
        print(f"Compte créé : {email}")
    UserRepo.set_role(user.id, "admin")
    UserRepo.set_email_verified(user.id)
    print(f"✅ {email} est administrateur (publication gratuite, accès admin)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
