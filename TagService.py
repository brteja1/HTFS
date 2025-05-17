from TagHandler import DatabaseManager, TagRepository, ResourceRepository

class TagService:
    """
    High-level service to manage tags and resources using repositories.
    """
    def __init__(self, db_path):
        self.db_manager = DatabaseManager(db_path)
        self.db_manager.connect();
        self.tag_repo = TagRepository(self.db_manager)
        self.resource_repo = ResourceRepository(self.db_manager)

    def __del__(self):
        self.db_manager.close()

    def initialize(self):
        self.db_manager.initialize_schema()

    # Tag operations
    def add_tag(self, tag_name):
        return self.tag_repo.add_tag(tag_name)

    def rename_tag(self, tag_name, new_tag_name):
        return self.tag_repo.rename_tag(tag_name, new_tag_name)

    def link_tag(self, tag_name, tag_parent_name):
        return self.tag_repo.link_tag(tag_name, tag_parent_name)

    def unlink_tag(self, tag_name, tag_parent_name):
        return self.tag_repo.unlink_tag(tag_name, tag_parent_name)

    def get_tag_id(self, tag_name):
        return self.tag_repo.get_tag_id(tag_name)

    def get_tag_name(self, tag_id):
        return self.tag_repo.get_tag_name(tag_id)

    def get_tag_list(self):
        return self.tag_repo.get_tag_list()

    def get_tag_closure(self, tags):
        return self.tag_repo.get_tag_closure(tags)

    # Resource operations
    def add_resource(self, resource_url):
        return self.resource_repo.add_resource(resource_url)

    def get_resource_id(self, resource_url):
        return self.resource_repo.get_resource_id(resource_url)

    def get_resource_url(self, res_id):
        return self.resource_repo.get_resource_url(res_id)

    def get_resource_ids(self):
        return self.resource_repo.get_resource_ids()

    def update_resource_url(self, resource_url, new_resource_url):
        return self.resource_repo.update_resource_url(resource_url, new_resource_url)

    def del_resource(self, resource_url):
        return self.resource_repo.del_resource(resource_url)

    def add_resource_tags(self, resource_url, tags):
        tag_ids = [self.tag_repo.get_tag_id(tag) for tag in tags]
        return self.resource_repo.add_resource_tags(resource_url, tag_ids)

    def del_resource_tags(self, resource_url, tags):
        tag_ids = [self.tag_repo.get_tag_id(tag) for tag in tags]
        return self.resource_repo.del_resource_tags(resource_url, tag_ids)

    def get_resource_tags(self, resource_url):
        tag_ids = self.resource_repo.get_resource_tags(resource_url)
        return [self.tag_repo.get_tag_name(tid) for tid in tag_ids]

    def get_resources_by_tag(self, tags):
        tag_ids = [self.tag_repo.get_tag_id(tag) for tag in tags]
        return self.resource_repo.get_resources_by_tag_id(tag_ids)

