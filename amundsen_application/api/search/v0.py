import logging
import json

from http import HTTPStatus

from typing import Any, Dict, Optional  # noqa: F401

from flask import Response, jsonify, make_response, request
from flask import current_app as app
from flask.blueprints import Blueprint

from amundsen_application.log.action_log import action_logging
from amundsen_application.api.utils.request_utils import get_query_param, request_search
from amundsen_application.api.utils.response_utils import create_error_response
from amundsen_application.api.utils.search_utils import generate_query_json, map_table_result, valid_search_fields
from amundsen_application.models.user import load_user, dump_user

LOGGER = logging.getLogger(__name__)

REQUEST_SESSION_TIMEOUT_SEC = 3

search_blueprint = Blueprint('search', __name__, url_prefix='/api/search/v0')

SEARCH_ENDPOINT = '/search'
SEARCH_USER_ENDPOINT = '/search_user'


# TODO: To be deprecated pending full community support
def _validate_search_term(*, search_term: str, page_index: int) -> Optional[Response]:
    error_payload = {
        'results': [],
        'search_term': search_term,
        'total_results': 0,
        'page_index': page_index,
    }
    # use colon means user would like to search on specific fields
    if search_term.count(':') > 1:
        message = 'Encountered error: Search field should not be more than 1'
        return create_error_response(message=message, payload=error_payload, status_code=HTTPStatus.BAD_REQUEST)
    if search_term.count(':') == 1:
        field_key = search_term.split(' ')[0].split(':')[0]
        if field_key not in valid_search_fields:
            message = 'Encountered error: Search field is invalid'
            return create_error_response(message=message, payload=error_payload, status_code=HTTPStatus.BAD_REQUEST)
    return None


# TODO: To be deprecated pending full community support
@search_blueprint.route('/table', methods=['GET'])
def search_table() -> Response:
    search_term = get_query_param(request.args, 'query', 'Endpoint takes a "query" parameter')
    page_index = get_query_param(request.args, 'page_index', 'Endpoint takes a "page_index" parameter')

    error_response = _validate_search_term(search_term=search_term, page_index=int(page_index))
    if error_response is not None:
        return error_response

    results_dict = _search_table(search_term=search_term, page_index=page_index)
    return make_response(jsonify(results_dict), results_dict.get('status_code', HTTPStatus.INTERNAL_SERVER_ERROR))


# TODO: To be deprecated pending full community support
@action_logging
def _search_table(*, search_term: str, page_index: int) -> Dict[str, Any]:
    """
    call the search service endpoint and return matching results
    :return: a json output containing search results array as 'results'

    Schema Defined Here:
    https://github.com/lyft/amundsensearchlibrary/blob/master/search_service/api/search.py

    TODO: Define an interface for envoy_client
    """
    tables = {
        'page_index': int(page_index),
        'results': [],
        'total_results': 0,
    }

    results_dict = {
        'search_term': search_term,
        'msg': '',
        'tables': tables,
    }

    try:
        if ':' in search_term:
            url = _create_url_with_field(search_term=search_term,
                                         page_index=page_index)
        else:
            url = '{0}?query_term={1}&page_index={2}'.format(app.config['SEARCHSERVICE_BASE'] + SEARCH_ENDPOINT,
                                                             search_term,
                                                             page_index)

        response = request_search(url=url)
        status_code = response.status_code

        if status_code == HTTPStatus.OK:
            results_dict['msg'] = 'Success'
            results = response.json().get('results')
            tables['results'] = [map_table_result(result) for result in results]
            tables['total_results'] = response.json().get('total_results')
        else:
            message = 'Encountered error: Search request failed'
            results_dict['msg'] = message
            logging.error(message)

        results_dict['status_code'] = status_code
        return results_dict
    except Exception as e:
        message = 'Encountered exception: ' + str(e)
        results_dict['msg'] = message
        logging.exception(message)
        return results_dict


# TODO: To be deprecated pending full community support
def _create_url_with_field(*, search_term: str, page_index: int) -> str:
    """
    Construct a url by searching specific field.
    E.g if we use search tag:hive test_table, search service will first
    filter all the results that
    don't have tag hive; then it uses test_table as query term to search /
    rank all the documents.

    We currently allow max 1 field.
    todo: allow search multiple fields(e.g tag:hive & schema:default test_table)

    :param search_term:
    :param page_index:
    :return:
    """
    # example search_term: tag:tag_name search_term search_term2
    fields = search_term.split(' ')
    search_field = fields[0].split(':')
    field_key = search_field[0]
    # dedup tag to all lower case
    field_val = search_field[1].lower()
    search_term = ' '.join(fields[1:])
    url = '{0}/field/{1}/field_val/{2}' \
          '?page_index={3}'.format(app.config['SEARCHSERVICE_BASE'] + SEARCH_ENDPOINT,
                                   field_key,
                                   field_val,
                                   page_index)
    if search_term:
        url += '&query_term={0}'.format(search_term)
    return url


@search_blueprint.route('/table_qs', methods=['POST'])
def search_table_query_string() -> Response:
    """
    TODO (ttannis): Update this docstring after amundsensearch documentation is merged
    Calls the search service to execute a search. The request data is transformed
    to the json payload defined [link]
    """
    request_json = request.get_json()

    search_term = get_query_param(request_json, 'term', '"term" parameter expected in request data')
    page_index = get_query_param(request_json, 'pageIndex', '"pageIndex" parameter expected in request data')
    filters = request_json.get('filters', {})

    # Default results
    tables = {
        'page_index': int(page_index),
        'results': [],
        'total_results': 0,
    }
    results_dict = {
        'search_term': search_term,
        'msg': '',
        'tables': tables,
    }

    try:
        query_json = generate_query_json(filters=filters, page_index=page_index, search_term=search_term)
    except Exception as e:
        message = 'Encountered exception generating query json: ' + str(e)
        results_dict['msg'] = message
        logging.exception(message)
        return make_response(jsonify(results_dict), HTTPStatus.INTERNAL_SERVER_ERROR)

    try:
        # TODO (ttannis): Change actual endpoint name after amundsensearch PR is merged
        url = app.config['SEARCHSERVICE_BASE'] + '/search_table'
        response = request_search(url=url,
                                  headers={'Content-Type': 'application/json'},
                                  method='POST',
                                  data=json.dumps(query_json))
        status_code = response.status_code
        if status_code == HTTPStatus.OK:
            results_dict['msg'] = 'Success'
            results = response.json().get('results')
            tables['results'] = [map_table_result(result) for result in results]
            tables['total_results'] = response.json().get('total_results')
        else:
            message = 'Encountered error: Search request failed'
            results_dict['msg'] = message
            logging.error(message)

        results_dict['status_code'] = status_code
        return make_response(jsonify(results_dict), status_code)
    except Exception as e:
        message = 'Encountered exception: ' + str(e)
        results_dict['msg'] = message
        logging.exception(message)
        return make_response(jsonify(results_dict), HTTPStatus.INTERNAL_SERVER_ERROR)


@search_blueprint.route('/user', methods=['GET'])
def search_user() -> Response:
    search_term = get_query_param(request.args, 'query', 'Endpoint takes a "query" parameter')
    page_index = get_query_param(request.args, 'page_index', 'Endpoint takes a "page_index" parameter')
    results_dict = _search_user(search_term=search_term, page_index=page_index)

    return make_response(jsonify(results_dict), results_dict.get('status_code', HTTPStatus.INTERNAL_SERVER_ERROR))


@action_logging
def _search_user(*, search_term: str, page_index: int) -> Dict[str, Any]:
    """
    call the search service endpoint and return matching results
    :return: a json output containing search results array as 'results'

    Schema Defined Here:
    https://github.com/lyft/amundsensearchlibrary/blob/master/search_service/api/user.py
    TODO: Define an interface for envoy_client
    """

    def _map_user_result(result: Dict) -> Dict:
        user_result = dump_user(load_user(result))
        user_result['type'] = 'user'
        return user_result

    users = {
        'page_index': int(page_index),
        'results': [],
        'total_results': 0,
    }

    results_dict = {
        'search_term': search_term,
        'msg': 'Success',
        'status_code': HTTPStatus.OK,
        'users': users,
    }

    try:
        url = '{0}?query_term={1}&page_index={2}'.format(app.config['SEARCHSERVICE_BASE'] + SEARCH_USER_ENDPOINT,
                                                         search_term,
                                                         page_index)

        response = request_search(url=url)
        status_code = response.status_code

        if status_code == HTTPStatus.OK:
            results_dict['msg'] = 'Success'
            results = response.json().get('results')
            users['results'] = [_map_user_result(result) for result in results]
            users['total_results'] = response.json().get('total_results')
        else:
            message = 'Encountered error: Search request failed'
            results_dict['msg'] = message
            logging.error(message)

        results_dict['status_code'] = status_code
        return results_dict
    except Exception as e:
        message = 'Encountered exception: ' + str(e)
        results_dict['msg'] = message
        logging.exception(message)
        return results_dict


# TODO - Implement
def _search_dashboard(*, search_term: str, page_index: int) -> Dict[str, Any]:
    return {}
