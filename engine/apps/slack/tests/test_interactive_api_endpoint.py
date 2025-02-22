import json
from unittest.mock import call, patch

import pytest
from django.conf import settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.slack.scenarios.scenario_step import PAYLOAD_TYPE_BLOCK_ACTIONS

EVENT_TRIGGER_ID = "5333959822612.4122782784722.4734ff484b2ac4d36a185bb242ee9932"
WARNING_TEXT = (
    "OnCall is not able to process this action because one of the following scenarios: \n"
    "1. The Slack chatops integration was disconnected from the instance that the Alert Group belongs "
    "to, BUT the Slack workspace is still connected to another instance as well. In this case, simply log "
    "in to the OnCall web interface and re-install the Slack Integration with this workspace again.\n"
    "2. (Less likely) The Grafana instance belonging to this Alert Group was deleted. In this case the Alert Group is orphaned and cannot be acted upon."
)

SLACK_TEAM_ID = "T043LP0P2M8"
SLACK_ACCESS_TOKEN = "asdfasdf"
SLACK_BOT_ACCESS_TOKEN = "cmncvmnvcnm"
SLACK_BOT_USER_ID = "mncvnmvcmnvcmncv,,cx,"

SLACK_USER_ID = "iurtiurituritu"


def _make_request(payload):
    return APIClient().post(
        "/slack/interactive_api_endpoint/",
        format="json",
        data=payload,
        **{
            "HTTP_X_SLACK_SIGNATURE": "asdfasdf",
            "HTTP_X_SLACK_REQUEST_TIMESTAMP": "xxcxcvx",
        },
    )


@pytest.fixture
def slack_team_identity(make_slack_team_identity):
    return make_slack_team_identity(
        slack_id=SLACK_TEAM_ID,
        detected_token_revoked=None,
        access_token=SLACK_ACCESS_TOKEN,
        bot_access_token=SLACK_BOT_ACCESS_TOKEN,
        bot_user_id=SLACK_BOT_USER_ID,
    )


@patch("apps.slack.views.SlackEventApiEndpointView.verify_signature", return_value=True)
@patch("apps.slack.views.SlackEventApiEndpointView._open_warning_window_if_needed")
@pytest.mark.django_db
def test_organization_not_found_scenario_properly_handled(
    mock_open_warning_window_if_needed,
    _mock_verify_signature,
    make_organization,
    make_slack_user_identity,
    slack_team_identity,
):
    # SCENARIO 1
    # two orgs connected to same slack workspace, the one belonging to the alert group/slack message
    # is no longer connected to the slack workspace, but another org still is
    make_slack_user_identity(slack_team_identity=slack_team_identity, slack_id=SLACK_USER_ID)

    make_organization(slack_team_identity=slack_team_identity)
    org2 = make_organization()
    event_payload_actions = [
        {
            "value": json.dumps({"organization_id": org2.id}),
        }
    ]

    event_payload = {
        "type": PAYLOAD_TYPE_BLOCK_ACTIONS,
        "trigger_id": EVENT_TRIGGER_ID,
        "user": {
            "id": SLACK_USER_ID,
        },
        "team": {
            "id": SLACK_TEAM_ID,
        },
        "actions": event_payload_actions,
    }

    response = _make_request(event_payload)
    assert response.status_code == status.HTTP_200_OK

    # SCENARIO 2
    # the org that was associated w/ the alert group, has since been deleted
    # and the slack message is now orphaned
    org2.hard_delete()

    response = _make_request(event_payload)
    assert response.status_code == status.HTTP_200_OK

    mock_call = call(event_payload, slack_team_identity, WARNING_TEXT)
    mock_open_warning_window_if_needed.assert_has_calls([mock_call, mock_call])


@patch("apps.slack.views.SlackEventApiEndpointView.verify_signature", return_value=True)
@patch("apps.slack.views.SlackEventApiEndpointView._open_warning_window_if_needed")
@pytest.mark.django_db
def test_organization_not_found_scenario_doesnt_break_slash_commands(
    mock_open_warning_window_if_needed,
    _mock_verify_signature,
    make_organization,
    make_slack_user_identity,
    slack_team_identity,
):

    make_organization(slack_team_identity=slack_team_identity)
    make_slack_user_identity(slack_team_identity=slack_team_identity, slack_id=SLACK_USER_ID)

    response = _make_request(
        {
            "token": "axvnc,mvc,mv,mcvmnxcmnxc",
            "team_id": SLACK_TEAM_ID,
            "team_domain": "testingtest-nim4013",
            "channel_id": "C043HQ70QMB",
            "channel_name": "testy-testing",
            "user_id": "U043HQ3VABF",
            "user_name": "bob.smith",
            "command": settings.SLACK_DIRECT_PAGING_SLASH_COMMAND,
            "text": "potato",
            "api_app_id": "A0909234092340293402934234234234234234",
            "is_enterprise_install": "false",
            "response_url": "https://hooks.slack.com/commands/cvcv/cvcv/cvcv",
            "trigger_id": "asdfasdf.4122782784722.cvcv",
        }
    )

    assert response.status_code == status.HTTP_200_OK
    mock_open_warning_window_if_needed.assert_not_called()
