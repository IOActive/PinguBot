
"""Report upload task."""

import time

from pingu_sdk.datastore import crash_uploader, data_handler
from pingu_sdk.metrics import logs
from pingu_sdk.system import environment, errors
from pingu_sdk.datastore.models import ReportMetadata


def execute_task(*_):
    """Execute the report uploads."""
    logs.log('Uploading pending reports.')

    # Get metadata for reports requiring upload.
    reports_metadata = list(ReportMetadata)
    if not reports_metadata:
        logs.log('No reports that need upload found.')
        return

    environment.set_value('UPLOAD_MODE', 'prod')

    # Otherwise, upload corresponding reports.
    logs.log('Uploading reports for testcases: %s' % str(
        [report.testcase_id for report in reports_metadata]))

    report_metadata_to_delete = []
    for report_metadata in reports_metadata:
        # Convert metadata back into actual report.
        crash_info = crash_uploader.crash_report_info_from_metadata(report_metadata)
        testcase_id = report_metadata.testcase_id

        try:
            _ = data_handler.get_testcase_by_id(testcase_id)
        except errors.InvalidTestcaseError:
            logs.log_warn('Could not find testcase %s.' % testcase_id)
            report_metadata_to_delete.append(report_metadata.key)
            continue

        # Upload the report and update the corresponding testcase info.
        logs.log('Processing testcase %s for crash upload.' % testcase_id)
        crash_report_id = crash_info.upload()
        if crash_report_id is None:
            logs.log_error(
                'Crash upload for testcase %s failed, retry later.' % testcase_id)
            continue

        # Update the report metadata to indicate successful upload.
        report_metadata.crash_report_id = crash_report_id
        report_metadata.is_uploaded = True
        report_metadata.put()

        logs.log('Uploaded testcase %s to crash, got back report id %s.' %
                 (testcase_id, crash_report_id))
        time.sleep(1)

    # Delete report metadata entries where testcase does not exist anymore or
    # upload is not supported.
    if report_metadata_to_delete:
        data_handler.delete_multi(report_metadata_to_delete)

    # Log done with uploads.
    # Deletion happens in batches in cleanup_task, so that in case of error there
    # is some buffer for looking at stored ReportMetadata in the meantime.
    logs.log('Finished uploading crash reports.')
