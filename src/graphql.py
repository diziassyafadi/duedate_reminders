from pprint import pprint

import requests
import config


def get_repo_issues(owner, repository, duedate_field_name, after=None, issues=None):
    query = """
    query GetRepoIssues($owner: String!, $repo: String!, $after: String) {
      repository(owner: $owner, name: $repo) {
        issues(first: 100, after: $after, states: [OPEN]) {
          nodes {
            id
            title
            number
            url
            assignees(first:100) {
              nodes {
                name
                email
                login
              }
            }
            projectItems(first: 10) {
              nodes {
                project {
                  number
                  title
                }
                fieldValues(first: 20) {
                  nodes {
                    ... on ProjectV2ItemFieldDateValue {
                      field { ... on ProjectV2FieldCommon { name } }
                      date
                    }
                    ... on ProjectV2ItemFieldSingleSelectValue {
                      field { ... on ProjectV2FieldCommon { name } }
                      name
                    }
                  }
                }
              }
            }
          }
          pageInfo {
            endCursor
            hasNextPage
          }
          totalCount
        }
      }
    }
    """

    variables = {
        'owner': owner,
        'repo': repository,
        'after': after
    }

    response = requests.post(
        config.api_endpoint,
        json={"query": query, "variables": variables},
        headers={"Authorization": f"Bearer {config.gh_token}"}
    )

    if response.json().get('errors'):
        print(response.json().get('errors'))

    repo_data = response.json().get("data", {}).get("repository", {})
    if not repo_data:
        return []

    issues_nodes = repo_data.get("issues", {}).get("nodes", [])
    pageinfo = repo_data.get("issues", {}).get("pageInfo", {})

    if issues is None:
        issues = []

    issues.extend(issues_nodes)

    if pageinfo.get("hasNextPage"):
        return get_repo_issues(
            owner=owner,
            repository=repository,
            duedate_field_name=duedate_field_name,
            after=pageinfo.get("endCursor"),
            issues=issues
        )

    return issues



def get_project_issues(owner, owner_type, project_number, duedate_field_name, filters=None, after=None, issues=None):
    query = f"""
    query GetProjectIssues($owner: String!, $projectNumber: Int!, $duedate: String!, $after: String)  {{
      {owner_type}(login: $owner) {{
        projectV2(number: $projectNumber) {{
          id
          title
          number
          items(first: 100, after: $after) {{
            nodes {{
              id
              fieldValueByName(name: $duedate) {{
                ... on ProjectV2ItemFieldDateValue {{
                  id
                  date
                }}
              }}
              fieldValueByName(name: "Status") {{
                ... on ProjectV2ItemFieldSingleSelectValue {{
                  id
                  name
                }}
              }}
              content {{
                ... on Issue {{
                  id
                  title
                  number
                  state
                  url
                  assignees(first:20) {{
                    nodes {{
                      name
                      email
                      login
                    }}
                  }}
                }}
              }}
            }}
            pageInfo {{
              endCursor
              hasNextPage
              hasPreviousPage
            }}
            totalCount
          }}
        }}
      }}
    }}
    """

    variables = {
        'owner': owner,
        'projectNumber': project_number,
        'duedate': duedate_field_name,
        'after': after
    }

    response = requests.post(
        config.api_endpoint,
        json={"query": query, "variables": variables},
        headers={"Authorization": f"Bearer {config.gh_token}"}
    )

    if response.json().get('errors'):
        print(response.json().get('errors'))

    pageinfo = (
        response.json()
        .get('data')
        .get(owner_type)
        .get('projectV2')
        .get('items')
        .get('pageInfo')
    )
    if issues is None:
        issues = []

    nodes = (
        response.json()
        .get('data')
        .get(owner_type)
        .get('projectV2')
        .get('items')
        .get('nodes')
    )

    if filters:
        filtered_issues = []
        for node in nodes:
            if filters.get('open_only') and node['content'].get('state') != 'OPEN':
                continue
            if filters.get('empty_duedate') and node['fieldValueByName']:
                continue
            if filters.get('status') and (
                not node.get('fieldValueByName') or
                node['fieldValueByName'].get('name') != filters['status']
            ):
                continue
            filtered_issues.append(node)
        nodes = filtered_issues

    issues = issues + nodes

    if pageinfo.get('hasNextPage'):
        return get_project_issues(
            owner=owner,
            owner_type=owner_type,
            project_number=project_number,
            after=pageinfo.get('endCursor'),
            filters=filters,
            issues=issues,
            duedate_field_name=duedate_field_name
        )

    return issues



def add_issue_comment(issueId, comment):
    mutation = """
    mutation AddIssueComment($issueId: ID!, $comment: String!) {
        addComment(input: {subjectId: $issueId, body: $comment}) {
            clientMutationId
        }
    }
    """

    variables = {
        'issueId': issueId,
        'comment': comment
    }
    response = requests.post(
        config.api_endpoint,
        json={"query": mutation, "variables": variables},
        headers={"Authorization": f"Bearer {config.gh_token}"}
    )
    if response.json().get('errors'):
        print(response.json().get('errors'))

    return response.json().get('data')
