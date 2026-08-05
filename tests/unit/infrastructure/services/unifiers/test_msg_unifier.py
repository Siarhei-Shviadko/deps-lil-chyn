from deps_lil_chyn.domain.dto import ContainerType


def test_unify_msg(msg_unifier, fake_storage_service):
    sender = "Palina Pashkouskaya1 <Palina_Pashkouskaya1@epam.com>"
    cc = ["Palina Pashkouskaya1 <Palina_Pashkouskaya1@epam.com>"]
    recipients = ["Palina Pashkouskaya1 <Palina_Pashkouskaya1@epam.com>"]
    subject = "Test email"
    body = "Test email"
    file_path = "tests/data/test_email.msg"
    attachment_titles = ("image001.png", "attachment1.pdf", "attachment2.pdf")

    with open(file_path, "r+b") as f:
        fake_storage_service.upload(path=file_path, content=f.read(), replace_if_exists=True)

    unified_container_data = msg_unifier.unify(file_path)

    assert unified_container_data.container_type == ContainerType.EMAIL
    assert len(unified_container_data.attachments) == len(attachment_titles)

    for attachment, expected_attachment_title in zip(unified_container_data.attachments, attachment_titles):
        assert attachment.title == expected_attachment_title
        assert fake_storage_service.download(attachment.blob_name)

    assert unified_container_data.container_metadata.sender == sender
    assert unified_container_data.container_metadata.cc == cc
    assert unified_container_data.container_metadata.recipients == recipients
    assert unified_container_data.container_metadata.subject == subject
    assert body in unified_container_data.container_metadata.body
