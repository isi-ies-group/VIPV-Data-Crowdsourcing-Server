from flaskr.web import web_bp
from flaskr.common_user import (
    CredentialsValidator,
    get_user_by_email,
    valid_login,
    register_user,
)
from flaskr.common_files import (
    get_files_for_user,
    get_file_for_user_by_name,
    get_sessions_dir_for_user,
)

from flask import (
    render_template,
    request,
    redirect,
    jsonify,
    send_file,
    Response,
    current_app,
)

from flask_jwt_extended import (
    create_access_token,
    jwt_required,
    get_jwt_identity,
    set_access_cookies,
    unset_jwt_cookies,
)
# import folium

from logging import warning


@web_bp.route("/", methods=["GET"])
def index():
    """
    Index page
    """
    return render_template("index.html")


@web_bp.route("/isLoggedIn", methods=["GET"])
@jwt_required(optional=True)
def is_logged_in():
    """
    Check if the user is logged in
    """
    return jsonify({"isLoggedIn": get_jwt_identity() is not None})


@web_bp.route("/login", methods=["GET", "POST"])
@jwt_required(optional=True)
def login():
    """
    This function handles the login page
    """
    # Check if the user is already logged in
    if get_jwt_identity():
        return redirect("/profile")

    if request.method == "GET":  # On GET request, return the login page
        return render_template("login.html")
    elif request.method == "POST":  # On POST request, check if the user is valid
        # Get credentials from the form
        email = request.form["email"]
        password = request.form["password"]

        # Validate login
        try:
            user = valid_login(email, password=password)
        except ValueError:
            return render_template("login.html", error_message="Contraseña incorrecta")
        except TypeError:
            return render_template("login.html", error_message="Usuario no registrado")

        # If the password is correct, log the user in
        access_token = create_access_token(identity=user.email)
        response = redirect("/profile")
        set_access_cookies(response, access_token)
        return response


@web_bp.route("/logout", methods=["GET", "POST"])
def logout():
    """
    Logout to landing page
    """
    response = redirect("/")
    unset_jwt_cookies(response)
    return response


@web_bp.route("/signup", methods=["GET", "POST"])
@jwt_required(optional=True)
def signup():
    """
    Register a new user
    """
    # Check if the user is already logged in
    if get_jwt_identity():
        return redirect("/profile")

    if request.method == "GET":  # On GET request, return the register page
        return render_template("signup.html")
    elif request.method == "POST":  # On POST request, register the user
        # Get credentials from the form
        email = request.form["email"].lower()
        password = request.form["password"]
        username = request.form["username"]

        # Validate credentials
        if not CredentialsValidator.validate_email(email):
            return render_template("signup.html", error_message="Email inválido")

        if not CredentialsValidator.validate_password(password):
            return render_template(
                "signup.html",
                error_message=(
                    "Contraseña inválida." + "Debe contener entre 8 y 20 caracteres."
                ),
            )

        if not CredentialsValidator.validate_username(username):
            return render_template(
                "signup.html",
                error_message=(
                    "Nombre de usuario inválido. "
                    + "Debe contener entre 5 y 20 caracteres."
                ),
            )

        # Create the user
        try:
            register_user(usermail=email, username=username, password=password)
        except ValueError:
            return render_template("signup.html", error_message="Email ya registrado")

        # Log the user in with JWT token
        access_token = create_access_token(identity=email)
        response = redirect("/profile")
        set_access_cookies(response, access_token)
        return response


@web_bp.route("/profile", methods=["GET"])
@jwt_required(optional=True)
def profile():
    """
    Profile page of the user
    """
    current_user = get_jwt_identity()

    # Redirect to login if the user is not logged in
    if not current_user:
        return redirect("/login")

    # Get the user
    user = get_user_by_email(current_user)
    user_files = get_files_for_user(user)

    # TODO: add files to the template
    return render_template(
        "profile.html", user=user, user_files=user_files, n_files=len(user_files)
    )


@web_bp.route("/profile/download_session", methods=["GET"])
@jwt_required(optional=False)
def download_session():
    """
    Download a session file with example URL:

    /profile/download_session?filename=...
    """
    # Get the file id
    requested_filename = request.args.get("filename")
    if not requested_filename:
        return redirect("/profile")

    # Get the user
    current_user = get_jwt_identity()
    user = get_user_by_email(current_user)

    # Get the filename from the database
    file = get_file_for_user_by_name(user, requested_filename)
    if not file:
        warning(
            f"User {user.email} tried to download a file that does not belong to them."
        )
        return redirect("/profile")

    # Get the filepath
    filepath = get_sessions_dir_for_user(user) / file.filename

    # Download the file
    return send_file(filepath, mimetype="text/plain", as_attachment=True)


@web_bp.route("/profile/session_map", methods=["GET"])
@jwt_required(optional=True)
def session_map():
    """
    Session map page of the user
    """
    # Check if the user is logged in
    if not get_jwt_identity():
        return redirect("/login")

    # Get the user
    current_user = get_jwt_identity()
    user = get_user_by_email(current_user)

    # Get the sessions for the user
    user_files = get_files_for_user(user)

    # Render the map page with the user's files
    return render_template("session_map.html", user_files=user_files)

'''  # TODO: use folium to show a map of the user's routes
@web_bp.route("/profile/map", methods=["GET"])
def map():
    """
    Map page of the user
    """
    # Check if the user is logged in
    if "usermail" not in session:
        return redirect("/login")

    return render_template("map.html")
'''


@web_bp.route("/about", methods=["GET"])
def about():
    """
    About page
    """
    return render_template("about.html")


@web_bp.route("/get-involved", methods=["GET"])
def get_involved():
    """
    Get involved page
    """
    return render_template("get-involved.html")


@web_bp.route("/privacy-policy", methods=["GET"])
def privacy_policy():
    language = request.args.get("lang", "en")

    policy = (
        current_app.config["PRIVACY_POLICY"]["texts"][language]
        or current_app.config["PRIVACY_POLICY"]["texts"]["en"]
    )
    last_updated = current_app.config["PRIVACY_POLICY"]["last-updated"]
    filename = f"privacy_policy_{language}_{last_updated}.txt"
    return Response(
        policy,
        mimetype="text/plain",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
