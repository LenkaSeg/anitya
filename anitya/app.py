# -*- coding: utf-8 -*-

"""
This module is responsible for creating and configuring the flask application
object. This includes loading any provided configuration and merging it with
the default configuration, loading and configuring Flask extensions, and
configuring logging.

User-facing Flask routes should be placed in the ``anitya.ui`` module and API
routes should be placed in ``anitya.api_v2``.
"""

import logging
import logging.config
import logging.handlers

import flask
from flask_login import LoginManager, current_user, user_logged_in
from flask import url_for, render_template
from authlib.integrations.flask_client import OAuth
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import NoResultFound

<<<<<<< HEAD
=======
from anitya.config import config as anitya_config
from anitya.db import Session, initialize as initialize_db, models
from anitya.lib import utilities
from . import ui, admin, api, api_v2, authentication, auth
>>>>>>> ffbba79 (Migrate social_auth to authlib)
import anitya.lib
import anitya.mail_logging
from anitya import __version__
from anitya.config import config as anitya_config
from anitya.db import Session
from anitya.db import initialize as initialize_db
from anitya.db import models
from anitya.lib import utilities

from . import admin, api, api_v2, authentication, ui


def create(config=None):
    """
    Create and configure a Flask application object.

    Args:
        config (dict): The configuration to use when creating the application.
            If no configuration is provided, :data:`anitya.config.config` is
            used.

    Returns:
        flask.Flask: The configured Flask application.
    """
    app = flask.Flask(__name__)

    if config is None:
        config = anitya_config
    app.config.update(config)
    initialize_db(config)

    login_manager = LoginManager()
    login_manager.user_loader(authentication.load_user_from_session)
    login_manager.request_loader(authentication.load_user_from_request)
    login_manager.login_view = "/login/"
    login_manager.init_app(app)

    # Register the v2 API resources
    packages_view = api_v2.PackagesResource.as_view("apiv2.packages")
    app.add_url_rule(
        "/api/v2/packages/", view_func=packages_view, methods=["GET", "POST"]
    )
    projects_view = api_v2.ProjectsResource.as_view("apiv2.projects")
    app.add_url_rule(
        "/api/v2/projects/", view_func=projects_view, methods=["GET", "POST"]
    )
    versions_view = api_v2.VersionsResource.as_view("apiv2.versions")
    app.add_url_rule(
        "/api/v2/versions/", view_func=versions_view, methods=["GET", "POST"]
    )

    # Register all the view blueprints
    app.register_blueprint(ui.ui_blueprint)
    app.register_blueprint(api.api_blueprint)

    oauth = OAuth(app)
    for auth_backend in app.config.get("AUTHLIB_ENABLED_BACKENDS", []):
        oauth.register(auth_backend.lower())

    app.register_blueprint(auth.create_oauth_blueprint(oauth))

    app.before_request(global_user)
    app.teardown_request(shutdown_session)
    app.register_error_handler(IntegrityError, integrity_error_handler)
    # TODO: Need to change for authlib
    #app.register_error_handler(AuthException, auth_error_handler)

    app.context_processor(inject_variable)

    # subscribe to signals
    user_logged_in.connect(when_user_log_in, app)

    if app.config.get("EMAIL_ERRORS"):
        # If email logging is configured, set up the anitya logger with an email
        # handler for any ERROR-level logs.
        _anitya_log = logging.getLogger("anitya")
        _anitya_log.addHandler(
            anitya.mail_logging.get_mail_handler(
                smtp_server=app.config.get("SMTP_SERVER"),
                mail_admin=app.config.get("ADMIN_EMAIL"),
            )
        )

    return app


def global_user():
    """Set the flask.g variables using the session information if the user is logged in."""
    flask.g.user = current_user._get_current_object()  # pylint: disable=W0212


def shutdown_session(exception=None):
    """Remove the DB session at the end of each request."""
    Session.remove()


def inject_variable():
    """Inject into all templates variables that we would like to have all
    the time.
    """
    justedit = flask.session.get("justedit", False)
    if justedit:  # pragma: no cover
        flask.session["justedit"] = None

    cron_status = utilities.get_last_cron(Session)

    return dict(
        version=__version__,
        is_admin=admin.is_admin(),
        justedit=justedit,
        cron_status=cron_status,
        user=current_user,
        available_backends=anitya_config["AUTHLIB_ENABLED_BACKENDS"],
    )


def integrity_error_handler(error):
    """
    Flask error handler for unhandled IntegrityErrors.

    Args:
        error (IntegrityError): The exception to be handled.

    Returns:
        tuple: A tuple of (message, HTTP error code).
    """
    # Because social auth provides the route and raises the exception, this is
    # the simplest way to turn the error into a nicely formatted error message
    # for the user.
    if "email" in error.params:
        Session.rollback()
        other_user = models.User.query.filter_by(email=error.params["email"]).one()
        try:
            social_auth_user = other_user.oauth.filter_by(
                user_id=other_user.id
            ).one()
            msg = (
                "Error: There's already an account associated with your email, "
                f"authenticate with {social_auth_user.provider}."
            )
            return msg, 400
        # This error happens only if there is account without provider info
        except NoResultFound:
            Session.delete(other_user)
            Session.commit()
            msg = (
                "Error: There was already an existing account with missing provider. "
                "So we removed it. "
                "Please try to log in again."
            )
            return msg, 500

    return "The server encountered an unexpected error", 500


def auth_error_handler(error):
    """
    Flask error handler for unhandled AuthException errors.

    Args:
        error (AuthException): The exception to be handled.

    Returns:
        tuple: A tuple of (message, HTTP error code).
    """
    # Because social auth openId backend provides route and raises the exceptions,
    # this is the simplest way to turn error into nicely formatted error message.
    msg = (
        f"Error: There was an error during authentication '{error}', "
        "please check the provided url."
    )
    return msg, 400


def when_user_log_in(sender, user):
    """
    This catches the signal when user is logged in.
    It checks if the user has associated entry in user_social_auth.

    Args:
        sender (flask.Flask): Current app object that emitted signal.
            Not used by this method.
        user (models.User): User that is logging in.

    Raises:
        sqlalchemy.exc.IntegrityError: When user_social_auth table entry is
        missing.
    """
    # TODO: new social table need to be added
    #if user.oauth.count() == 0:
    #    raise IntegrityError(
    #        "Missing authlib table",
    #        {"authlib": None, "email": user.email},
    #        None,
    #    )
